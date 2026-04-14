// scripting_stub.cc — no-op ScriptInterpreter for Linux builds without Tcl
//
// Replaces scripting/scriptinterpreter.cc and scripting/tcl.cc entirely.
// ScriptInterpreterFactory returns a NullInterpreter whose RunScript() is a no-op.

#include <scripting/scriptinterpreter.hp>

//=============================================================================

ScriptInterpreter::ScriptInterpreter(MailboxesManager& manager)
    : _mailboxesManager(manager)
{
}

ScriptInterpreter::~ScriptInterpreter()
{
}

void ScriptInterpreter::Validate()
{
}

void ScriptInterpreter::AddConstantArray(IntArrayEntry* /*entryList*/)
{
}

void ScriptInterpreter::DeleteConstantArray(IntArrayEntry* /*entryList*/)
{
}

//=============================================================================

class NullInterpreter : public ScriptInterpreter
{
public:
    NullInterpreter(MailboxesManager& mgr) : ScriptInterpreter(mgr) {}
    ~NullInterpreter() {}

    Scalar RunScript(const void* /*script*/, int /*objectIndex*/) override
    {
        return Scalar::FromFloat(0.0f);
    }
};

//=============================================================================

ScriptInterpreter* ScriptInterpreterFactory(MailboxesManager& mailboxesManager, Memory& memory)
{
    return new (memory) NullInterpreter(mailboxesManager);
}
