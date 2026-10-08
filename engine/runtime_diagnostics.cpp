#include "runtime_diagnostics.hpp"
#ifdef WF_RUNTIME_DIAGNOSTICS
#define JSON_NOEXCEPTION 1
#include "../third_party/json/nlohmann/json.hpp"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <deque>
#include <map>
#include <mutex>
#include <set>
#include <thread>
#include <arpa/inet.h>
#include <fcntl.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>
#include <cerrno>

namespace wfdiag {
namespace {
using Json=nlohmann::json;
constexpr size_t MaxLine=4096, MaxReply=65536, MaxOutput=262144;
constexpr size_t MaxClients=8, MaxPending=64, MaxPerClient=16;
constexpr uint64_t MaxInteger=9007199254740991ULL;
int64_t now() { return std::chrono::duration_cast<std::chrono::microseconds>(
    std::chrono::steady_clock::now().time_since_epoch()).count(); }
struct Input {
    struct Consumer { uint32_t actor;uint64_t generation;int mailbox; };
    uint64_t sequence=0, frame=0, step=0; int64_t time=0;
    std::string source, route="pending", reason="awaiting-route";
    uint32_t held=0, pressed=0, released=0; int code=0;
    bool routed=false, consumed=false;
    std::vector<Consumer> consumers;
};
struct InputState {
    uint64_t received=0, routed=0, consumed=0, lastPress=0, lastRelease=0;
    uint32_t held=0; bool focus=true;
    std::string route="none", reason="no-input";
    std::map<std::string,uint32_t> sources;
    std::deque<Input> history;
};
struct Reply { Request request; State state; Snapshot snapshot; InputState input; std::string error; };
struct Peer {
    int fd=-1; uint64_t serial=0; std::string input, output;
    size_t sent=0; int64_t writeSince=0;
    std::set<uint64_t> inflight;
};
std::mutex mutex;
State latest;
InputState inputs;
std::deque<Request> pending;
std::deque<Reply> replies;
std::map<const void*,uint64_t> actors;
uint64_t actorSerial=0;
std::atomic<bool> running{false};
std::thread worker;
int listener=-1, boundPort=0;
// Process identity persists through level transitions and listener restarts.
const std::string run=std::to_string(getpid())+"-"+std::to_string(now());

Json envelope(const Request& r,const State& s) {
    return {{"v",1},{"request",r.id},{"run",run},{"level_generation",s.levelGeneration},
            {"monotonic_us",s.monotonicUs},{"frame",s.frame},{"simulation_step",s.step}};
}
Json actorJson(const ActorState& a) {
    if(!a.available) return nullptr;
    return {{"actor",a.actor},{"generation",a.generation},{"position",a.position},
            {"velocity",a.velocity},{"active",a.active},{"visible",a.visible}};
}
std::string encode(const Reply& r) {
    Json j=envelope(r.request,r.state);
    if(!r.error.empty()) {
        j["op"]="error";j["error"]=r.error;
    } else {
        j["op"]="snapshot";
        j["game"]={{"level",r.state.level},{"mode",r.state.mode},{"focus",r.input.focus},
            {"paused",r.state.paused},{"suspended",r.state.suspended},
            {"modal",r.state.modal},{"session",r.state.session},{"cursor",r.state.cursor}};
        j["player"]=actorJson(r.snapshot.player);j["selected"]=actorJson(r.snapshot.selected);
        const auto& p=r.snapshot.properties;
        j["properties"]=nullptr;
        if(p.available) {
            Json f=Json::array();
            for(const auto& v:p.fields) {
                Json field={{"id",p.schema+":"+std::to_string(v.id)},
                            {"field",v.id},{"key",v.key},{"committed",v.committed}};
                if(r.request.draft&&p.draftOpen)field["draft"]=v.draft;
                f.push_back(std::move(field));
            }
            j["properties"]={{"actor",p.actor},{"generation",p.generation},{"revision",p.revision},
                {"schema",p.schema},{"fields",f},{"truncated",p.truncated}};
            if(r.request.draft)j["properties"]["edit"]={{"open",p.draftOpen},{"session",p.session},{"error",p.error}};
        }
        const auto& i=r.input;
        Json events=Json::array();
        for(const auto& e:i.history)if(e.sequence>r.request.sinceInput) {
            Json consumers=Json::array();
            for(const auto& c:e.consumers)consumers.push_back({{"actor",c.actor},{"generation",c.generation},{"mailbox",c.mailbox}});
            events.push_back({{"received",e.sequence},{"monotonic_us",e.time},{"source",e.source},
                {"held",e.held},{"pressed",e.pressed},{"released",e.released},{"code",e.code},
                {"routed",e.routed},{"consumed",e.consumed},{"route",e.route},{"reason",e.reason},
                {"frame",e.frame},{"simulation_step",e.step},{"consumers",consumers}});
        }
        uint64_t oldest=i.history.empty()?i.received+1:i.history.front().sequence;
        j["input"]={{"received",i.received},{"routed",i.routed},{"consumed",i.consumed},
            {"held",i.held},{"sources",i.sources},{"last_press",i.lastPress},{"last_release",i.lastRelease},
            {"route",i.route},{"reason",i.reason},{"oldest_receipt",oldest},
            {"gap",r.request.sinceInput<oldest-1},{"history",events}};
    }
    std::string line=j.dump(-1,' ',false,Json::error_handler_t::replace);
    if(line.size()>MaxReply) {
        j=envelope(r.request,r.state);j["op"]="error";j["error"]="reply-too-large";
        line=j.dump();
    }
    return line+'\n';
}
Reply failure(const Request& r,const std::string& error) {
    std::lock_guard<std::mutex> lock(mutex);
    Reply reply;reply.request=r;reply.state=latest;reply.error=error;return reply;
}
bool queueOutput(Peer& p,const Reply& reply) {
    auto line=encode(reply);
    if(p.output.size()-p.sent+line.size()>MaxOutput)return false;
    if(p.sent){p.output.erase(0,p.sent);p.sent=0;}
    if(p.output.empty())p.writeSince=now();
    p.output+=line;return true;
}
bool parse(const std::string& line,Request& r,std::string& error) {
    // Bound nesting before the recursive JSON parser. Request values are flat.
    int depth=0;bool quoted=false,escape=false;
    for(char c:line) {
        if(quoted){if(escape)escape=false;else if(c=='\\')escape=true;else if(c=='"')quoted=false;}
        else if(c=='"')quoted=true;
        else if(c=='{'||c=='['){if(++depth>2){error="malformed-request";return false;}}
        else if(c=='}'||c==']')--depth;
    }
    bool duplicate=false;std::set<std::string> keys;
    auto callback=[&](int,nlohmann::json::parse_event_t event,Json& value){
        if(event==Json::parse_event_t::key&&!keys.insert(value.get<std::string>()).second)duplicate=true;
        return true;
    };
    Json j=Json::parse(line,callback,false);
    if(j.is_discarded()||!j.is_object()||duplicate){error="malformed-request";return false;}
    auto integer=[&](const char* key,uint64_t& dest,bool required=false){
        auto it=j.find(key);if(it==j.end())return !required;
        if(!it->is_number_unsigned()&&!it->is_number_integer())return false;
        if(it->is_number_integer()&&it->get<int64_t>()<0)return false;
        dest=it->get<uint64_t>();return dest<=MaxInteger;
    };
    uint64_t version=0,actor=0,timeout=1000;
    if(!integer("request",r.id,true)||!r.id){error="invalid-request-id";return false;}
    if(!integer("v",version,true)||version!=1){error="unsupported-version";return false;}
    if(!j.contains("op")||!j["op"].is_string()){error="malformed-request";return false;}
    if(j["op"]!="snapshot"){error="read-only-operation";return false;}
    const std::set<std::string> allowed={"v","request","op","run","level_generation","actor",
        "actor_generation","after_frame","after_simulation_step","min_input","since_input","draft","timeout_ms"};
    for(auto it=j.begin();it!=j.end();++it)if(!allowed.count(it.key())){error="unknown-field";return false;}
    if(!integer("level_generation",r.levelGeneration)||!integer("actor_generation",r.actorGeneration)
       ||!integer("actor",actor)||actor>2047||!integer("after_frame",r.afterFrame)
       ||!integer("after_simulation_step",r.afterStep)||!integer("min_input",r.minInput)
       ||!integer("since_input",r.sinceInput)||!integer("timeout_ms",timeout)||timeout<1||timeout>5000){
        error="invalid-field";return false;
    }
    r.actor=int(actor);r.waitFrame=j.contains("after_frame");r.waitStep=j.contains("after_simulation_step");
    if((r.actor&&!r.actorGeneration)||(r.actorGeneration&&!r.actor)
       ||((r.waitFrame||r.waitStep||r.actor)&&!r.levelGeneration)){
        error="generation-required";return false;
    }
    if(j.contains("draft")){if(!j["draft"].is_boolean()){error="invalid-field";return false;}r.draft=j["draft"].get<bool>();}
    if(j.contains("run")){if(!j["run"].is_string()){error="invalid-field";return false;}r.run=j["run"].get<std::string>();}
    r.deadline=now()+int64_t(timeout)*1000;return true;
}
void removePeer(std::vector<Peer>& peers,size_t index) {
    const auto client=peers[index].serial;
    close(peers[index].fd);peers.erase(peers.begin()+index);
    std::lock_guard<std::mutex> lock(mutex);
    pending.erase(std::remove_if(pending.begin(),pending.end(),[&](const Request& r){return r.client==client;}),pending.end());
    replies.erase(std::remove_if(replies.begin(),replies.end(),[&](const Reply& r){return r.request.client==client;}),replies.end());
}
void loop() {
    std::vector<Peer> peers;uint64_t serial=0;
    while(running.load()) {
        std::deque<Reply> ready;
        {
            std::lock_guard<std::mutex> lock(mutex);
            ready.swap(replies);
            for(auto it=pending.begin();it!=pending.end();) {
                if(now()>=it->deadline) {
                    Reply reply;reply.request=*it;reply.state=latest;reply.error="timeout";
                    ready.push_back(std::move(reply));it=pending.erase(it);
                } else ++it;
            }
        }
        for(auto& p:peers)for(const auto& r:ready)if(r.request.client==p.serial) {
            p.inflight.erase(r.request.id);
            if(!queueOutput(p,r))shutdown(p.fd,SHUT_RDWR);
        }
        std::vector<pollfd> fds;fds.push_back({listener,POLLIN,0});
        for(const auto& p:peers)fds.push_back({p.fd,short(POLLIN|(p.output.empty()?0:POLLOUT)),0});
        if(poll(fds.data(),fds.size(),10)<0&&errno!=EINTR)break;
        // Handle the polled peers before accepting new ones (stable indices).
        for(size_t n=peers.size();n>0;--n) {
            size_t index=n-1;auto& p=peers[index];short ev=fds[index+1].revents;
            bool alive=!(ev&(POLLERR|POLLHUP|POLLNVAL));
            if(alive&&ev&POLLIN) {
                char bytes[4096];ssize_t count=recv(p.fd,bytes,sizeof(bytes),0);
                if(count==0)alive=false;
                else if(count<0){if(errno!=EAGAIN&&errno!=EWOULDBLOCK&&errno!=EINTR)alive=false;}
                else {
                    p.input.append(bytes,size_t(count));size_t nl;
                    while(alive&&(nl=p.input.find('\n'))!=std::string::npos) {
                        if(nl>MaxLine){alive=false;break;}
                        std::string line=p.input.substr(0,nl);p.input.erase(0,nl+1);
                        Request r;r.client=p.serial;std::string error;
                        if(!parse(line,r,error))alive=queueOutput(p,failure(r,error));
                        else if(p.inflight.count(r.id)) { alive=false; } // ambiguous IDs terminate the session
                        else if(p.inflight.size()>=MaxPerClient)alive=queueOutput(p,failure(r,"queue-full"));
                        else {
                            bool accepted=false;
                            size_t outstanding=0;
                            for(const auto& peer:peers)outstanding+=peer.inflight.size();
                            {
                                std::lock_guard<std::mutex> lock(mutex);
                                if(outstanding<MaxPending){pending.push_back(r);accepted=true;}
                            }
                            if(accepted)p.inflight.insert(r.id);
                            else alive=queueOutput(p,failure(r,"queue-full"));
                        }
                    }
                    if(p.input.size()>MaxLine)alive=false;
                }
            }
            if(alive&&ev&POLLOUT&&!p.output.empty()) {
                ssize_t count=send(p.fd,p.output.data()+p.sent,p.output.size()-p.sent,MSG_NOSIGNAL);
                if(count>0){p.sent+=size_t(count);if(p.sent==p.output.size()){p.output.clear();p.sent=0;}}
                else if(count<0&&errno!=EAGAIN&&errno!=EWOULDBLOCK&&errno!=EINTR)alive=false;
            }
            if(!p.output.empty()&&now()-p.writeSince>2000000)alive=false;
            if(!alive)removePeer(peers,index);
        }
        if(fds[0].revents&POLLIN) {
            int fd=accept(listener,nullptr,nullptr);
            if(fd>=0) {
                if(peers.size()>=MaxClients||fcntl(fd,F_SETFL,O_NONBLOCK)<0)close(fd);
                else {Peer peer;peer.fd=fd;peer.serial=++serial;peers.push_back(std::move(peer));}
            }
        }
    }
    for(auto& p:peers)close(p.fd);
}
}
bool Start(int port) {
    if(running)return true;
    if(port<0||port>65535)return false;
    int fd=socket(AF_INET,SOCK_STREAM,0);if(fd<0)return false;
    int yes=1;setsockopt(fd,SOL_SOCKET,SO_REUSEADDR,&yes,sizeof(yes));
    sockaddr_in address{};address.sin_family=AF_INET;address.sin_port=htons(uint16_t(port));address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
    if(bind(fd,reinterpret_cast<sockaddr*>(&address),sizeof(address))<0||listen(fd,8)<0||fcntl(fd,F_SETFL,O_NONBLOCK)<0){close(fd);return false;}
    socklen_t size=sizeof(address);getsockname(fd,reinterpret_cast<sockaddr*>(&address),&size);
    listener=fd;boundPort=ntohs(address.sin_port);running=true;worker=std::thread(loop);return true;
}
void Stop() {
    running=false;if(worker.joinable())worker.join();
    if(listener>=0)close(listener);
    listener=-1;boundPort=0;
    std::lock_guard<std::mutex> lock(mutex);pending.clear();replies.clear();
}
int Port(){return boundPort;}
void Pump(const State& boundary,const std::function<Snapshot(const Request&)>& capture) {
    State s=boundary;s.monotonicUs=now();
    std::deque<Request> requests;InputState input;
    {
        std::lock_guard<std::mutex> lock(mutex);latest=s;
        if(pending.empty())return;
        input=inputs;requests.swap(pending);
    }
    size_t budget=4; // bound actor/property copying per rendering boundary
    for(const auto& r:requests) {
        if(!budget){std::lock_guard<std::mutex> lock(mutex);pending.push_back(r);continue;}
        --budget;
        Reply reply;reply.request=r;reply.state=s;reply.input=input;
        const Input* acknowledged=nullptr;
        if(r.minInput)for(const auto& entry:input.history)if(entry.sequence==r.minInput){acknowledged=&entry;break;}
        const bool waitingInput=r.minInput&&(!acknowledged||!acknowledged->consumed);
        if(!r.run.empty()&&r.run!=run)reply.error="stale-run";
        else if(r.levelGeneration&&r.levelGeneration!=s.levelGeneration)reply.error="stale-level";
        else if(now()>=r.deadline)reply.error="timeout";
        else if(r.minInput&&!acknowledged&&r.minInput<=input.received)reply.error="input-gap";
        else if((r.waitStep||waitingInput)&&s.suspended)reply.error="suspended";
        else if(r.waitStep&&s.paused)reply.error="simulation-paused";
        else if((r.waitFrame&&s.frame<=r.afterFrame)||(r.waitStep&&s.step<=r.afterStep)||waitingInput) {
            std::lock_guard<std::mutex> lock(mutex);pending.push_back(r);continue;
        } else {reply.snapshot=capture(r);reply.error=reply.snapshot.error;}
        std::lock_guard<std::mutex> lock(mutex);replies.push_back(std::move(reply));
    }
}
void Boundary(const State& s){std::lock_guard<std::mutex> lock(mutex);latest=s;latest.monotonicUs=now();}
uint64_t Receive(const char* source,uint32_t held,uint32_t pressed,uint32_t released,int code) {
    std::lock_guard<std::mutex> lock(mutex);
    // Mask samplers observe transitions; explicit key events also record repeats
    // and unmapped/intercepted keys, even when the held mask is unchanged.
    if(!code&&!pressed&&!released&&inputs.sources[source]==held)return inputs.received;
    Input e;e.sequence=++inputs.received;e.time=now();e.source=source;e.held=held;
    uint32_t previous=inputs.sources[e.source];e.pressed=pressed|(held&~previous);e.released=released|(previous&~held);e.code=code;
    inputs.sources[e.source]=held;inputs.held=0;
    for(const auto& entry:inputs.sources)inputs.held|=entry.second;
    if(e.pressed)inputs.lastPress=e.sequence;
    if(e.released)inputs.lastRelease=e.sequence;
    inputs.history.push_back(e);if(inputs.history.size()>MaxInputHistory)inputs.history.pop_front();return e.sequence;
}
void Consume(const char* route,const char* reason,uint32_t /*held*/,uint64_t receipt) {
    std::lock_guard<std::mutex> lock(mutex);
    inputs.route=route;inputs.reason=reason;
    for(auto& e:inputs.history)if(!e.consumed&&(!receipt||e.sequence==receipt)) {
        e.routed=true;e.consumed=true;e.route=route;e.reason=reason;e.frame=latest.frame;e.step=latest.step;
        inputs.routed=std::max(inputs.routed,e.sequence);inputs.consumed=std::max(inputs.consumed,e.sequence);
    }
}
void Route(const char* route,const char* reason,uint64_t receipt) {
    std::lock_guard<std::mutex> lock(mutex);inputs.route=route;inputs.reason=reason;
    for(auto& e:inputs.history)if(!e.routed&&(!receipt||e.sequence==receipt)) {
        e.routed=true;e.route=route;e.reason=reason;e.frame=latest.frame;e.step=latest.step;
        inputs.routed=std::max(inputs.routed,e.sequence);
    }
}
void InputRead(uint32_t actor,uint64_t generation,int mailbox) {
    std::lock_guard<std::mutex> lock(mutex);
    for(auto it=inputs.history.rbegin();it!=inputs.history.rend();++it) {
        auto& e=*it;
        if(e.consumed&&e.route=="game"&&e.step!=latest.step)break;
        if(e.route!="game"||e.source=="lifecycle")continue;
        e.routed=e.consumed=true;e.reason="actor-input-read";e.frame=latest.frame;e.step=latest.step;
        inputs.routed=std::max(inputs.routed,e.sequence);inputs.consumed=std::max(inputs.consumed,e.sequence);
        inputs.route="game";inputs.reason=e.reason;
        bool seen=false;for(const auto& c:e.consumers)if(c.actor==actor&&c.generation==generation&&c.mailbox==mailbox)seen=true;
        if(!seen&&e.consumers.size()<8)e.consumers.push_back({actor,generation,mailbox});
    }
}
void Focus(bool focused){std::lock_guard<std::mutex> lock(mutex);inputs.focus=focused;}
void ActorCreated(const void* actor){actors[actor]=++actorSerial;}
void ActorDeleted(const void* actor){actors.erase(actor);}
uint64_t ActorGeneration(const void* actor){auto it=actors.find(actor);return it==actors.end()?0:it->second;}
}
#endif
