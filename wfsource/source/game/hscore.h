#pragma once
// High-score persistence for Q*bert — top-N scores saved to qbert_hiscores.txt.
// Only compiled in DESIGNER_CHEATS builds (Linux dev).

static constexpr int HS_COUNT = 23;

struct HiScore
{
    int  score;
    int  round;
    char name[4];  // NUL-terminated 3-char initials
};

extern HiScore g_hiscores[HS_COUNT];

// Load from qbert_hiscores.txt in the working directory.
// Idempotent: no-op after the first successful call.
// Zero-fills on missing or corrupt file.
void HScore_Load();

// Write g_hiscores to qbert_hiscores.txt.
void HScore_Save();

// Return true if score beats the lowest entry.
bool HScore_IsHigh(int score);

// Insert (score, round, name) into g_hiscores in descending order.
// Lowest entry is dropped. Does not save — call HScore_Save() after.
void HScore_Insert(int score, int round, const char* name);
