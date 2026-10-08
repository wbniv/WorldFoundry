// Real sockets + the production bridge, without a level or GL context.
#include "debug_server.hp"
#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>
#include <cstdio>
#include <cstdlib>
#include <string>

static void check(bool ok, const char* what)
{
    if (!ok) { std::perror(what); std::exit(1); }
}

static int connect_client(int port)
{
    int fd = ::socket(AF_INET, SOCK_STREAM, 0);
    check(fd >= 0, "client socket");
    timeval timeout { 2, 0 };
    ::setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    sockaddr_in addr {};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = htons(port);
    check(::connect(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) == 0,
          "reconnect");
    return fd;
}

static void request(int fd, const char* line, const char* expected)
{
    const std::string message(line);
    check(::send(fd, message.data(), message.size(), 0) == ssize_t(message.size()), "send");
    std::string reply;
    char ch;
    while (reply.empty() || reply.back() != '\n') {
        check(::read(fd, &ch, 1) == 1, "reply after reconnect");
        reply += ch;
    }
    check(reply == expected, "unexpected reply");
}

int main()
{
    int reservation = ::socket(AF_INET, SOCK_STREAM, 0);
    check(reservation >= 0, "port reservation");
    sockaddr_in addr {};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    check(::bind(reservation, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) == 0, "bind");
    socklen_t len = sizeof(addr);
    check(::getsockname(reservation, reinterpret_cast<sockaddr*>(&addr), &len) == 0, "port");
    const int port = ntohs(addr.sin_port);
    // A failed start must release its socket and permit a later successful start.
    DebugServer_Start(port);
    DebugServer_Stop();
    ::close(reservation);
    for (int cycle = 0; cycle < 200; ++cycle) {
        // Exercise Stop before the new listener gets a chance to run.
        DebugServer_Start(port);
        DebugServer_Stop();
        DebugServer_Start(port);
        int client = connect_client(port);
        request(client, "{\"op\":\"ping\"}\n", "{\"op\":\"pong\"}\n");
        request(client, "{\"op\":\"pause\"}\n", "{\"op\":\"paused\"}\n");
        check(DebugServer_IsPaused(), "pause");
        int idle = connect_client(port);
        // Keep one reader blocked with an incomplete command at teardown.
        check(::send(idle, "{\"op\":", 6, 0) == 6, "partial command");
        DebugServer_Stop();
        check(!DebugServer_IsPaused(), "pause leaked into next level");
        DebugServer_Start(port);
        int next = connect_client(port);
        request(next, "{\"op\":\"ping\"}\n", "{\"op\":\"pong\"}\n");
        char ch;
        check(::read(client, &ch, 1) == 0, "old connection stayed open");
        ::close(client);
        ::close(idle);
        DebugServer_Stop();
        ::close(next);
        DebugServer_Stop(); // idempotent
    }
    // macOS/BSD does not wake a blocked accept() on shutdown(listen_fd), unlike
    // Linux; Stop used to wait for that listener forever (the 2026-10-08 macOS
    // Release smoke hung for 56 minutes in UnloadLevel). Imitate it here: with the
    // wake-up skipped, Stop must still return. SIGALRM turns a hang into a failure.
    ::setenv("WF_DEBUG_NO_LISTENER_WAKE", "1", 1);
    ::alarm(10);
    DebugServer_Start(port);
    DebugServer_Stop();
    ::alarm(0);
    ::unsetenv("WF_DEBUG_NO_LISTENER_WAKE");
    std::puts("PASS: 200 rapid restart cycles, blocked clients, pause reset, bind failure recovery, Stop without a listener wake-up");
}
