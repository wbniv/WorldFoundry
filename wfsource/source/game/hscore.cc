#include "hscore.h"
#include <cstdio>
#include <cstring>
#include <algorithm>

HiScore g_hiscores[HS_COUNT] = {};

static bool s_loaded = false;
static const char* kHiScoreFile = "qbert_hiscores.txt";

// All 23 arcade ROM factory defaults (from attract-mode HIGH SCORES screen).
static const HiScore kDefaults[HS_COUNT] = {
    { 3000, 0, "TJC" },
    { 2500, 0, "JML" },
    { 2000, 0, "JAH" },
    { 1750, 0, "MJS" },
    { 1500, 0, "ECW" },
    { 1250, 0, "BLT" },
    { 1000, 0, "BMW" },
    {  950, 0, "DMV" },
    {  900, 0, "FDA" },
    {  825, 0, "LMG" },
    {  800, 0, "DDT" },
    {  775, 0, "JCM" },
    {  750, 0, "ZAP" },
    {  725, 0, "NAB" },
    {  700, 0, "JUN" },
    {  675, 0, "HFR" },
    {  650, 0, "RON" },
    {  625, 0, "FXS" },
    {  600, 0, "DLB" },
    {  575, 0, "LEE" },
    {  550, 0, "CPB" },
    {  525, 0, "WBD" },
    {  500, 0, "SAM" },
};

void HScore_Load()
{
    if (s_loaded) return;
    s_loaded = true;

    FILE* f = fopen(kHiScoreFile, "rb");
    if (!f)
    {
        // No save file yet — seed with arcade defaults.
        memcpy(g_hiscores, kDefaults, sizeof(g_hiscores));
        return;
    }

    size_t n = fread(g_hiscores, sizeof(HiScore), HS_COUNT, f);
    fclose(f);

    if (n != (size_t)HS_COUNT)
        memcpy(g_hiscores, kDefaults, sizeof(g_hiscores));
}

void HScore_Save()
{
    FILE* f = fopen(kHiScoreFile, "wb");
    if (!f) return;
    fwrite(g_hiscores, sizeof(HiScore), HS_COUNT, f);
    fclose(f);
}

bool HScore_IsHigh(int score)
{
    return score > g_hiscores[HS_COUNT - 1].score;
}

void HScore_Insert(int score, int round, const char* name)
{
    // Find insertion point (descending by score)
    int pos = HS_COUNT;
    for (int i = 0; i < HS_COUNT; ++i)
    {
        if (score > g_hiscores[i].score) { pos = i; break; }
    }
    if (pos == HS_COUNT) return;

    // Shift entries below pos down one slot
    for (int i = HS_COUNT - 1; i > pos; --i)
        g_hiscores[i] = g_hiscores[i - 1];

    g_hiscores[pos].score = score;
    g_hiscores[pos].round = round;
    strncpy(g_hiscores[pos].name, name, 3);
    g_hiscores[pos].name[3] = '\0';
}
