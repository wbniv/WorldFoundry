// pilot_core.cc — PILOT parser + frame-resumable VM. Pure C++ (no engine deps,
// no exceptions). See pilot_core.hp / docs/pilot-language.md.

#include "pilot_core.hp"

#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace pilot {

std::string fmtnum(double v)
{
    char buf[32];
    std::snprintf(buf, sizeof(buf), "%g", v);
    return std::string(buf);
}

// ─────────────────────────────────────────────────────────────────────────────
// Lexer

namespace {

struct Tok { char kind; std::string text; };   // kind: n(um) s(tr) i(d) o(p)

bool lex(const std::string& s, std::vector<Tok>& out)
{
    size_t i = 0;
    while (i < s.size()) {
        char c = s[i];
        if (std::isspace((unsigned char)c)) { ++i; continue; }
        if (i + 1 < s.size()) {
            std::string two = s.substr(i, 2);
            if (two == "<=" || two == ">=" || two == "<>" || two == "//") {
                out.push_back({'o', two}); i += 2; continue;
            }
        }
        if (std::strchr("+-*/()<>=,&|!", c)) {
            out.push_back({'o', std::string(1, c)}); ++i; continue;
        }
        if (c == '"') {
            size_t j = i + 1;
            while (j < s.size() && s[j] != '"') ++j;
            out.push_back({'s', s.substr(i + 1, j - i - 1)});
            i = (j < s.size()) ? j + 1 : j;
            continue;
        }
        bool numStart = std::isdigit((unsigned char)c) ||
            (c == '.' && i + 1 < s.size() && std::isdigit((unsigned char)s[i + 1]));
        if (numStart) {
            size_t j = i;
            if (c == '0' && i + 1 < s.size() && (s[i + 1] == 'x' || s[i + 1] == 'X')) {
                j = i + 2;
                while (j < s.size() && std::isxdigit((unsigned char)s[j])) ++j;
            } else {
                while (j < s.size() && (std::isdigit((unsigned char)s[j]) || s[j] == '.')) ++j;
            }
            out.push_back({'n', s.substr(i, j - i)}); i = j; continue;
        }
        bool id0 = std::isalpha((unsigned char)c) || c == '_' || c == '#' || c == '$';
        if (id0) {
            size_t j = i + 1;
            while (j < s.size() &&
                   (std::isalnum((unsigned char)s[j]) || s[j] == '_')) ++j;
            out.push_back({'i', s.substr(i, j - i)}); i = j; continue;
        }
        return false;  // bad character
    }
    return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// Expression evaluator — recursive descent over the token stream.

struct Eval
{
    const std::vector<Tok>& t;
    size_t i = 0;
    VMState& st;
    PilotHost& host;
    int self;
    const ConstTable& consts;
    bool ok = true;

    Eval(const std::vector<Tok>& toks, VMState& s, PilotHost& h, int self_,
         const ConstTable& c) : t(toks), st(s), host(h), self(self_), consts(c) {}

    const std::string* peek() { return i < t.size() ? &t[i].text : nullptr; }
    bool isOp(const char* o) { return i < t.size() && t[i].kind == 'o' && t[i].text == o; }

    double resolve(const std::string& name)
    {
        if (!name.empty() && name[0] == '#') {
            auto it = st.num.find(name);
            return it != st.num.end() ? it->second : 0.0;
        }
        if (!name.empty() && name[0] == '$') {
            auto it = st.strv.find(name);
            if (it == st.strv.end()) return 0.0;
            return std::atof(it->second.c_str());
        }
        auto it = consts.find(name);
        if (it != consts.end()) return (double)it->second;
        ok = false;
        std::fprintf(stderr, "[pilot] unknown name '%s'\n", name.c_str());
        return 0.0;
    }

    double run()
    {
        double v = pOr();
        if (i != t.size()) { ok = false; }
        return v;
    }

    double pOr()
    {
        double v = pAnd();
        while (isOp("|")) { ++i; double r = pAnd(); v = (v != 0 || r != 0) ? 1 : 0; }
        return v;
    }
    double pAnd()
    {
        double v = pCmp();
        while (isOp("&")) { ++i; double r = pCmp(); v = (v != 0 && r != 0) ? 1 : 0; }
        return v;
    }
    double pCmp()
    {
        double v = pAdd();
        if (i < t.size() && t[i].kind == 'o') {
            const std::string& o = t[i].text;
            if (o == "=" || o == "<>" || o == "<" || o == "<=" || o == ">" || o == ">=") {
                ++i; double r = pAdd();
                bool b = (o == "=")  ? v == r : (o == "<>") ? v != r :
                         (o == "<")  ? v <  r : (o == "<=") ? v <= r :
                         (o == ">")  ? v >  r : v >= r;
                return b ? 1.0 : 0.0;
            }
        }
        return v;
    }
    double pAdd()
    {
        double v = pMul();
        while (isOp("+") || isOp("-")) {
            std::string o = t[i++].text; double r = pMul();
            v = (o == "+") ? v + r : v - r;
        }
        return v;
    }
    double pMul()
    {
        double v = pUnary();
        while (isOp("*") || isOp("/") || isOp("//")) {
            std::string o = t[i++].text; double r = pUnary();
            if (o == "*") v = v * r;
            else if (o == "/") v = (r != 0) ? v / r : 0.0;
            else v = ((long)r != 0) ? (double)((long)v / (long)r) : 0.0;  // // trunc int
        }
        return v;
    }
    double pUnary()
    {
        if (isOp("-")) { ++i; return -pUnary(); }
        if (isOp("!")) { ++i; return pUnary() != 0 ? 0.0 : 1.0; }
        return pPrimary();
    }
    double pPrimary()
    {
        if (i >= t.size()) { ok = false; return 0.0; }
        const Tok& tk = t[i++];
        if (tk.kind == 'n') {
            if (tk.text.size() > 1 && (tk.text[1] == 'x' || tk.text[1] == 'X'))
                return (double)strtol(tk.text.c_str(), nullptr, 16);
            return std::atof(tk.text.c_str());
        }
        if (tk.kind == 's') { ok = false; return 0.0; }   // string in numeric ctx
        if (tk.kind == 'o' && tk.text == "(") {
            double v = pOr();
            if (isOp(")")) ++i; else ok = false;
            return v;
        }
        if (tk.kind == 'i') {
            if (tk.text == "mb" && isOp("(")) {
                ++i;
                std::vector<double> args;
                args.push_back(pOr());
                while (isOp(",")) { ++i; args.push_back(pOr()); }
                if (isOp(")")) ++i; else ok = false;
                int mbx = (int)args[0];
                int actor = args.size() > 1 ? (int)args[1] : self;
                return host.ReadMailbox(actor, mbx);
            }
            return resolve(tk.text);
        }
        ok = false; return 0.0;
    }
};

double evalExpr(const std::string& text, VMState& st, PilotHost& host, int self,
                const ConstTable& consts)
{
    std::vector<Tok> toks;
    if (!lex(text, toks)) {
        std::fprintf(stderr, "[pilot] bad token in '%s'\n", text.c_str());
        return 0.0;
    }
    Eval e(toks, st, host, self, consts);
    double v = e.run();
    if (!e.ok)
        std::fprintf(stderr, "[pilot] eval error in '%s'\n", text.c_str());
    return v;
}

std::vector<std::string> splitWS(const std::string& s)
{
    std::vector<std::string> out;
    size_t i = 0;
    while (i < s.size()) {
        while (i < s.size() && std::isspace((unsigned char)s[i])) ++i;
        size_t j = i;
        while (j < s.size() && !std::isspace((unsigned char)s[j])) ++j;
        if (j > i) out.push_back(s.substr(i, j - i));
        i = j;
    }
    return out;
}

std::string trim(const std::string& s)
{
    size_t a = 0, b = s.size();
    while (a < b && std::isspace((unsigned char)s[a])) ++a;
    while (b > a && std::isspace((unsigned char)s[b - 1])) --b;
    return s.substr(a, b - a);
}

} // anonymous namespace

// ─────────────────────────────────────────────────────────────────────────────
// Parser

static const char* kVerbs[] = {
    "T","TH","A","M","C","J","U","E","EX","PA",
    "PS","PR","ST","IN","WM","WB","WT","SP","SF","SM",
    "WA","SH","SR","SG","PK","UD","RV","NW","DL","BT", nullptr
};

static bool isVerb(const std::string& h)
{
    for (int i = 0; kVerbs[i]; ++i) if (h == kVerbs[i]) return true;
    return false;
}

static bool decompose(const std::string& head, std::string& verb, char& cond)
{
    if (isVerb(head)) { verb = head; cond = 0; return true; }
    char last = head.empty() ? 0 : head.back();
    if ((last == 'Y' || last == 'N') && isVerb(head.substr(0, head.size() - 1))) {
        verb = head.substr(0, head.size() - 1); cond = last; return true;
    }
    return false;
}

Program parse(const char* src)
{
    Program p;
    std::string text(src ? src : "");
    size_t pos = 0;
    int lineno = 0;
    while (pos <= text.size()) {
        size_t nl = text.find('\n', pos);
        std::string raw = text.substr(pos, (nl == std::string::npos ? text.size() : nl) - pos);
        pos = (nl == std::string::npos) ? text.size() + 1 : nl + 1;
        ++lineno;
        std::string s = trim(raw);
        if (s.empty()) continue;

        // Remark / directive
        if (s.size() >= 2 && s[0] == 'R' && s[1] == ':') {
            std::string body = trim(s.substr(2));
            if (!body.empty() && body[0] == '@') {
                std::string rest = body.substr(1);
                size_t sp = rest.find_first_of(" \t");
                Directive d;
                d.key = (sp == std::string::npos) ? rest : rest.substr(0, sp);
                d.val = (sp == std::string::npos) ? "" : trim(rest.substr(sp));
                p.directives.push_back(d);
            }
            continue;
        }
        // Label, optionally followed by a statement.
        if (s[0] == '*') {
            size_t e = 1;
            while (e < s.size() && !std::isspace((unsigned char)s[e])) ++e;
            p.labels[s.substr(1, e - 1)] = (int)p.stmts.size();
            s = trim(s.substr(e));
            if (s.empty()) continue;
        }
        // Statement head: VERB[cond]['(' guard ')']':'
        size_t hp = 0;
        while (hp < s.size() && std::isalpha((unsigned char)s[hp])) ++hp;
        std::string head = s.substr(0, hp);
        std::string guard; bool hasGuard = false;
        size_t cur = hp;
        if (cur < s.size() && s[cur] == '(') {
            size_t close = s.find(')', cur);
            if (close == std::string::npos) {
                p.ok = false; p.error = "missing ) ";
                std::fprintf(stderr, "[pilot] line %d: missing )\n", lineno);
                continue;
            }
            guard = s.substr(cur + 1, close - cur - 1); hasGuard = true;
            cur = close + 1;
        }
        if (cur >= s.size() || s[cur] != ':') {
            p.ok = false;
            std::fprintf(stderr, "[pilot] line %d: not a statement: %s\n", lineno, s.c_str());
            continue;
        }
        std::string verb; char cond;
        if (!decompose(head, verb, cond)) {
            p.ok = false;
            std::fprintf(stderr, "[pilot] line %d: unknown verb '%s'\n", lineno, head.c_str());
            continue;
        }
        Stmt st;
        st.verb = verb; st.cond = cond; st.guard = guard; st.hasGuard = hasGuard;
        st.operand = s.substr(cur + 1);
        st.lineno = lineno;
        p.stmts.push_back(st);
    }
    return p;
}

// ─────────────────────────────────────────────────────────────────────────────
// VM

namespace {

enum ExecResult { CONTINUE, YIELD, HALT };

std::string interp(const std::string& text, VMState& st)
{
    std::string out;
    size_t i = 0;
    while (i < text.size()) {
        char c = text[i];
        if (c == '$' && i + 1 < text.size()) {
            if (text[i + 1] == '$') { out += '$'; i += 2; continue; }
            if (text[i + 1] == '#') {
                size_t j = i + 2;
                while (j < text.size() && (std::isalnum((unsigned char)text[j]) || text[j] == '_')) ++j;
                std::string name = "#" + text.substr(i + 2, j - (i + 2));
                auto it = st.num.find(name);
                out += fmtnum(it != st.num.end() ? it->second : 0.0);
                i = j; continue;
            }
            size_t j = i + 1;
            while (j < text.size() && (std::isalnum((unsigned char)text[j]) || text[j] == '_')) ++j;
            std::string name = "$" + text.substr(i + 1, j - (i + 1));
            auto it = st.strv.find(name);
            out += (it != st.strv.end()) ? it->second : std::string();
            i = j; continue;
        }
        out += c; ++i;
    }
    return out;
}

PilotHost::RelOp relopOf(const std::string& o)
{
    if (o == "=")  return PilotHost::RelOp::Eq;
    if (o == "<>") return PilotHost::RelOp::Ne;
    if (o == "<")  return PilotHost::RelOp::Lt;
    if (o == "<=") return PilotHost::RelOp::Le;
    if (o == ">")  return PilotHost::RelOp::Gt;
    return PilotHost::RelOp::Ge;
}

int labelIdx(const Program& prog, const std::string& operand)
{
    std::string name = trim(operand);
    if (!name.empty() && name[0] == '*') name = name.substr(1);
    auto it = prog.labels.find(name);
    if (it == prog.labels.end()) {
        std::fprintf(stderr, "[pilot] unknown label *%s\n", name.c_str());
        return -1;
    }
    return it->second;
}

ExecResult execStmt(const Program& prog, VMState& st, PilotHost& host, int self,
                    const ConstTable& consts, const Stmt& s)
{
    if (s.cond == 'Y' && !st.match) return CONTINUE;
    if (s.cond == 'N' && st.match) return CONTINUE;
    if (s.hasGuard && evalExpr(s.guard, st, host, self, consts) == 0) return CONTINUE;

    const std::string& v = s.verb;

    if (v == "T")  { host.Type(interp(s.operand, st), true);  return CONTINUE; }
    if (v == "TH") { host.Type(interp(s.operand, st), false); return CONTINUE; }

    if (v == "C") {
        size_t eq = s.operand.find('=');
        std::string lhs = trim(s.operand.substr(0, eq));
        std::string rhs = trim(eq == std::string::npos ? "" : s.operand.substr(eq + 1));
        if (lhs.rfind("mb", 0) == 0) {
            std::vector<Tok> toks;
            lex(lhs, toks);
            // toks: mb ( idx [, actor] )
            Eval e(toks, st, host, self, consts);
            e.i = 2;  // skip 'mb' '('
            int idx = (int)e.pOr();
            int actor = self;
            if (e.isOp(",")) { ++e.i; actor = (int)e.pOr(); }
            host.SetMailbox(actor, idx, evalExpr(rhs, st, host, self, consts));
        } else if (!lhs.empty() && lhs[0] == '$') {
            if (rhs.size() >= 2 && rhs.front() == '"' && rhs.back() == '"')
                st.strv[lhs] = rhs.substr(1, rhs.size() - 2);
            else
                st.strv[lhs] = fmtnum(evalExpr(rhs, st, host, self, consts));
        } else {
            st.num[lhs] = evalExpr(rhs, st, host, self, consts);
        }
        return CONTINUE;
    }

    if (v == "M") {
        std::string op = trim(s.operand);
        std::vector<Tok> toks; lex(op, toks);
        bool relational = false;
        for (auto& tk : toks)
            if (tk.kind == 'o' && (tk.text == "=" || tk.text == "<>" || tk.text == "<" ||
                tk.text == "<=" || tk.text == ">" || tk.text == ">=")) { relational = true; break; }
        if (relational) {
            st.match = evalExpr(op, st, host, self, consts) != 0;
        } else {
            st.match = false;
            std::string acc = trim(st.accept);
            size_t start = 0;
            while (start <= op.size()) {
                size_t comma = op.find(',', start);
                std::string item = trim(op.substr(start, (comma == std::string::npos ? op.size() : comma) - start));
                if (item == acc) { st.match = true; break; }
                if (comma == std::string::npos) break;
                start = comma + 1;
            }
        }
        return CONTINUE;
    }

    if (v == "J") { int l = labelIdx(prog, s.operand); if (l >= 0) st.pc = l; return CONTINUE; }
    if (v == "U") { int l = labelIdx(prog, s.operand); if (l >= 0) { st.callstack.push_back(st.pc); st.pc = l; } return CONTINUE; }
    if (v == "E") {
        if (!st.callstack.empty()) { st.pc = st.callstack.back(); st.callstack.pop_back(); return CONTINUE; }
        return HALT;
    }
    if (v == "EX") {
        st.exited = true;
        st.exitCode = trim(s.operand).empty() ? 0 : (int)evalExpr(s.operand, st, host, self, consts);
        return HALT;
    }

    if (v == "PA" || v == "WT") {
        double secs = evalExpr(s.operand, st, host, self, consts);
        st.awaitReq = PilotHost::AwaitReq();
        st.awaitReq.kind = PilotHost::AwaitKind::ClockSeconds;
        st.awaitReq.value = host.ClockSeconds() + secs;
        st.pendingAwait = true; st.awaitBind.clear();
        return YIELD;
    }

    if (v == "WM") {
        auto a = splitWS(s.operand);
        if (a.size() < 4) return CONTINUE;
        st.awaitReq = PilotHost::AwaitReq();
        st.awaitReq.kind = PilotHost::AwaitKind::Mailbox;
        st.awaitReq.actorIdx = (int)evalExpr(a[0], st, host, self, consts);
        st.awaitReq.mailbox  = (int)evalExpr(a[1], st, host, self, consts);
        st.awaitReq.op       = relopOf(a[2]);
        st.awaitReq.value    = evalExpr(a[3], st, host, self, consts);
        st.awaitReq.startSecs = host.ClockSeconds();
        for (size_t k = 0; k + 1 < a.size(); ++k)
            if (a[k] == "timeout") st.awaitReq.timeoutSecs = evalExpr(a[k + 1], st, host, self, consts);
        st.pendingAwait = true; st.awaitBind.clear();
        return YIELD;
    }

    if (v == "A") {
        // Accept: in-engine, await the engine. Bind into #last + named var.
        std::string var = trim(s.operand);
        st.awaitReq = PilotHost::AwaitReq();
        st.awaitReq.kind = PilotHost::AwaitKind::Mailbox;
        st.awaitReq.actorIdx = self;
        st.awaitReq.op = PilotHost::RelOp::Ne;   // satisfied on any nonzero change
        st.awaitReq.startSecs = host.ClockSeconds();
        st.pendingAwait = true; st.awaitBind = var;
        return YIELD;
    }

    if (v == "SM") {
        auto a = splitWS(s.operand);
        if (a.size() >= 3)
            host.SetMailbox((int)evalExpr(a[0], st, host, self, consts),
                            (int)evalExpr(a[1], st, host, self, consts),
                            evalExpr(a[2], st, host, self, consts));
        return CONTINUE;
    }
    if (v == "SP") {
        auto a = splitWS(s.operand);
        if (a.size() >= 4)
            host.SetTransform((int)evalExpr(a[0], st, host, self, consts),
                              evalExpr(a[1], st, host, self, consts),
                              evalExpr(a[2], st, host, self, consts),
                              evalExpr(a[3], st, host, self, consts));
        return CONTINUE;
    }
    if (v == "SF") {
        auto a = splitWS(s.operand);
        if (a.size() >= 3)
            host.SetProp((int)evalExpr(a[0], st, host, self, consts), a[1],
                         evalExpr(a[2], st, host, self, consts));
        return CONTINUE;
    }
    if (v == "IN") {
        auto a = splitWS(s.operand);
        if (a.size() >= 2) {
            int held = 0;
            for (size_t k = 0; k + 1 < a.size(); ++k)
                if (a[k] == "held") held = (int)evalExpr(a[k + 1], st, host, self, consts);
            host.InjectInput(a[0], (int)evalExpr(a[1], st, host, self, consts), held);
        }
        return CONTINUE;
    }

    // Bridge-only verbs — no-ops in-engine (an actor can't drive its own engine).
    if (v == "PS") { host.Pause();  return CONTINUE; }
    if (v == "PR") { host.Resume(); return CONTINUE; }
    if (v == "ST") { host.Step(trim(s.operand).empty() ? 1 : (int)evalExpr(s.operand, st, host, self, consts)); return CONTINUE; }
    if (v == "SH") { host.Screenshot(trim(s.operand)); return CONTINUE; }
    if (v == "WA") {
        auto a = splitWS(s.operand);
        if (a.size() >= 2)
            host.Watch((int)evalExpr(a[0], st, host, self, consts),
                       (int)evalExpr(a[1], st, host, self, consts),
                       a.size() > 2 && a[2] == "off");
        return CONTINUE;
    }
    // WB/SR/SG/PK/UD/RV/NW/DL/BT — accepted, no in-engine effect.
    return CONTINUE;
}

} // anonymous namespace

double run(const Program& prog, VMState& st, PilotHost& host, int self,
           const ConstTable& consts, int budget, bool* done)
{
    if (st.halted) { if (done) *done = true; return st.lastval; }

    // Resume a pending await (frame-resumable).
    if (st.pendingAwait) {
        double v = 0.0;
        PilotHost::AwaitState s = host.CheckAwait(st.awaitReq, v);
        if (s == PilotHost::AwaitState::Pending) { if (done) *done = false; return st.lastval; }
        st.num["#last"] = v;
        st.accept = fmtnum(v);
        if (!st.awaitBind.empty()) st.bind(st.awaitBind, v);
        st.lastval = v;
        st.pendingAwait = false; st.awaitBind.clear();
    }

    int n = 0;
    while (st.pc < (int)prog.stmts.size()) {
        if (++n > budget) { if (done) *done = false; return st.lastval; }  // yield on budget
        const Stmt& s = prog.stmts[st.pc++];
        ExecResult r = execStmt(prog, st, host, self, consts, s);
        if (r == YIELD) { if (done) *done = false; return st.lastval; }
        if (r == HALT)  { st.halted = true; break; }
        if (st.exited)  { st.halted = true; break; }
    }
    if (st.pc >= (int)prog.stmts.size()) st.halted = true;
    if (done) *done = st.halted;
    return st.lastval;
}

} // namespace pilot
