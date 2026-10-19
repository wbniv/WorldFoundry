// Phase-one read-only runtime diagnostics. Hooks disappear in ordinary builds.
#pragma once
#include <cstdint>
#ifdef WF_RUNTIME_DIAGNOSTICS
#include <array>
#include <functional>
#include <string>
#include <vector>

namespace wfdiag {
constexpr size_t MaxFields = 128, MaxInputHistory = 128;
struct Request {
    uint64_t client=0, id=0, levelGeneration=0, actorGeneration=0;
    uint64_t afterFrame=0, afterStep=0, minInput=0, sinceInput=0;
    int actor=0;
    bool draft=false, waitFrame=false, waitStep=false;
    std::string run;
    int64_t deadline=0;
};
struct ActorState {
    bool available=false, active=false, visible=false;
    int actor=0; uint64_t generation=0;
    std::array<float,3> position{}, velocity{};
};
struct FieldState {
    uint32_t id=0; std::string key, committed, draft;
};
struct Properties {
    bool available=false, draftOpen=false, truncated=false;
    uint32_t actor=0; uint64_t generation=0, revision=0, session=0;
    std::string schema, error;
    std::vector<FieldState> fields;
};
struct State {
    uint64_t levelGeneration=0, frame=0, step=0;
    int64_t monotonicUs=0;
    int level=-1;
    bool clockAvailable=false;
    float simulationTime=0, simulationDelta=0;
    bool focus=true, paused=false, suspended=false;
    std::string mode="loading", modal="none";
    uint64_t session=0;
    int cursor=-1;
};
struct Snapshot {
    ActorState player, selected;
    Properties properties;
    std::string error;
};
// Socket thread owns all descriptors. Only Pump's callback accesses engine state.
bool Start(int port);
void Stop();
int Port();
void Pump(const State&, const std::function<Snapshot(const Request&)>& capture);
void Boundary(const State&);
uint64_t Receive(const char* source, uint32_t held, uint32_t pressed=0,
                 uint32_t released=0, int code=0);
void Consume(const char* route, const char* reason, uint32_t held, uint64_t receipt=0);
void Route(const char* route, const char* reason, uint64_t receipt=0);
void InputRead(uint32_t actor, uint64_t generation, int mailbox);
void Focus(bool focused);
void ActorCreated(const void* actor);
void ActorDeleted(const void* actor);
uint64_t ActorGeneration(const void* actor);
}
#else
namespace wfdiag {
inline uint64_t Receive(const char*, uint32_t, uint32_t=0, uint32_t=0, int=0) { return 0; }
inline void Consume(const char*, const char*, uint32_t, uint64_t=0) {}
inline void Route(const char*, const char*, uint64_t=0) {}
inline void InputRead(uint32_t, uint64_t, int) {}
inline void Focus(bool) {}
inline void ActorCreated(const void*) {}
inline void ActorDeleted(const void*) {}
}
#endif
