#ifdef WF_ENABLE_STEAM

#include <hal/linux/steam.h>
#include <steam/steam_api.h>
#include <cstdio>

static bool s_initialized = false;

static InputActionSetHandle_t  s_setInGame   = 0;
static InputDigitalActionHandle_t s_jump      = 0;
static InputDigitalActionHandle_t s_grenade   = 0;
static InputDigitalActionHandle_t s_look      = 0;
static InputDigitalActionHandle_t s_angelMode = 0;
static InputDigitalActionHandle_t s_sword     = 0;
static InputDigitalActionHandle_t s_stepLeft  = 0;
static InputDigitalActionHandle_t s_stepRight = 0;
static InputDigitalActionHandle_t s_pause     = 0;
static InputAnalogActionHandle_t  s_move      = 0;

void _InitSteam()
{
    if (!SteamAPI_Init()) {
        fprintf(stderr, "WF Steam: SteamAPI_Init failed — running without Steam\n");
        return;
    }
    // bExplicitlyCallRunFrame=false: RunFrame is driven by SteamAPI_RunCallbacks()
    SteamInput()->Init(false);

    s_setInGame   = SteamInput()->GetActionSetHandle("InGame");
    s_jump        = SteamInput()->GetDigitalActionHandle("jump");
    s_grenade     = SteamInput()->GetDigitalActionHandle("grenade");
    s_look        = SteamInput()->GetDigitalActionHandle("look");
    s_angelMode   = SteamInput()->GetDigitalActionHandle("angel_mode");
    s_sword       = SteamInput()->GetDigitalActionHandle("sword");
    s_stepLeft    = SteamInput()->GetDigitalActionHandle("step_left");
    s_stepRight   = SteamInput()->GetDigitalActionHandle("step_right");
    s_pause       = SteamInput()->GetDigitalActionHandle("pause");
    s_move        = SteamInput()->GetAnalogActionHandle("move");

    s_initialized = true;
}

void _TermSteam()
{
    if (!s_initialized) return;
    SteamInput()->Shutdown();
    SteamAPI_Shutdown();
    s_initialized = false;
}

void _SteamRunCallbacks()
{
    if (!s_initialized) return;
    SteamAPI_RunCallbacks();
}

joystickButtonsF _GetSteamJoystickButtons()
{
    if (!s_initialized) return 0;

    joystickButtonsF buttons = 0;

    InputHandle_t controllers[STEAM_INPUT_MAX_COUNT];
    int count = SteamInput()->GetConnectedControllers(controllers);

    for (int i = 0; i < count; ++i) {
        InputHandle_t ctrl = controllers[i];
        SteamInput()->ActivateActionSet(ctrl, s_setInGame);

        auto dig = [&](InputDigitalActionHandle_t h) -> bool {
            return SteamInput()->GetDigitalActionData(ctrl, h).bState;
        };

        if (dig(s_jump))      buttons |= EJ_BUTTONF_A;
        if (dig(s_grenade))   buttons |= EJ_BUTTONF_B;
        if (dig(s_look))      buttons |= EJ_BUTTONF_C;
        if (dig(s_angelMode)) buttons |= EJ_BUTTONF_D;
        if (dig(s_sword))     buttons |= EJ_BUTTONF_E;
        if (dig(s_stepLeft))  buttons |= EJ_BUTTONF_G;
        if (dig(s_stepRight)) buttons |= EJ_BUTTONF_H;
        if (dig(s_pause))     buttons |= EJ_BUTTONF_K;

        static const float kDeadzone = 0.3f;
        InputAnalogActionData_t mv = SteamInput()->GetAnalogActionData(ctrl, s_move);
        if (mv.x < -kDeadzone) buttons |= EJ_BUTTONF_LEFT;
        if (mv.x >  kDeadzone) buttons |= EJ_BUTTONF_RIGHT;
        if (mv.y >  kDeadzone) buttons |= EJ_BUTTONF_UP;
        if (mv.y < -kDeadzone) buttons |= EJ_BUTTONF_DOWN;
    }

    return buttons;
}

#endif // WF_ENABLE_STEAM
