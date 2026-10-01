//=============================================================================
// game/level_menu_host.cc: a tiny host main for the level menu's tests (Linux)
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// tests/level_menu_harness.py compiles this file with level_menu.cc (and
// -DWF_LEVEL_MENU_HOST, ASan, UBSan) and feeds it one command per stdin line;
// the engine build globs this directory too, so without the define this file
// is empty. Commands and their answers:
//
//   bundle <cd.iff>        BUNDLE ok levels=N entries=M | BUNDLE none | BUNDLE error <why>
//                          then ENTRY <i> <level> <name> per entry, TITLE / PROMPT lines
//   synthetic <n> [<i> <long name>]   a bundle of n "Level k" entries (entry i renamed)
//   autopick               AUTO <level or -1>
//   menu <cursor> [tv]     a Menu over the bundle (tv: the remote's hint)
//   input <hex> <ms>       one frame of buttons; answers with a STATE line
//   rects <w> <h>          RECTS <count> changed=<0|1>, then R x0 y0 x1 y1 rrggbbaa
//   row <i>                ROW <text drawn for entry i>
//   script <text>          SCRIPT ok <frames> | SCRIPT error <why>
//   next                   FRAME <hex> back=<0|1> quit=<0|1> | FRAME end
//=============================================================================

#if defined(WF_LEVEL_MENU_HOST)

#include "level_menu.h"

#include <cstdio>
#include <fstream>
#include <iostream>
#include <iterator>
#include <memory>
#include <sstream>

using namespace levelmenu;

static void State(const Menu& m)
{
    std::printf("STATE cursor=%d first=%d chosen=%d done=%d level=%d\n", m.Cursor(), m.First(), m.Chosen() ? 1 : 0,
                m.Done() ? 1 : 0, m.GetBundle().entries.empty() ? -1 : m.ChosenLevel());
}

int main()
{
    std::setvbuf(stdout, nullptr, _IOLBF, 0);
    Bundle bundle;
    std::unique_ptr<Menu> menu;
    InputScript script;
    std::vector<PhonepadRect> rects;
    std::string line;
    while (std::getline(std::cin, line))
    {
        std::istringstream in(line);
        std::string cmd;
        in >> cmd;
        if (cmd == "bundle")
        {
            std::string path;
            in >> path;
            std::ifstream f(path, std::ios::binary);
            std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
            std::vector<TocEntry> toc;
            TocEntry menuEntry{};
            int levels = 0;
            std::string err;
            bundle = Bundle();
            if (!ParseToc(bytes.data(), bytes.size() < 2048 ? bytes.size() : 2048, &toc) || !FindMenu(toc, &menuEntry, &levels))
            {
                std::printf("BUNDLE none\n");
                continue;
            }
            if (size_t(menuEntry.offset) + menuEntry.size > bytes.size()
                || !ParseMenu(bytes.data() + menuEntry.offset, menuEntry.size, levels, &bundle, &err))
            {
                std::printf("BUNDLE error %s\n", err.empty() ? "MENU entry outside the file" : err.c_str());
                continue;
            }
            std::printf("TITLE %s\nPROMPT %s\n", bundle.title.c_str(), bundle.prompt.c_str());
            for (size_t i = 0; i < bundle.entries.size(); ++i)
                std::printf("ENTRY %zu %d %s\n", i, bundle.entries[i].level, bundle.entries[i].name.c_str());
            std::printf("BUNDLE ok levels=%d entries=%zu\n", levels, bundle.entries.size());
        }
        else if (cmd == "synthetic")
        {
            int n = 0, longAt = -1;
            in >> n >> longAt;
            std::string longName;
            std::getline(in, longName);
            if (!longName.empty() && longName[0] == ' ') longName.erase(0, 1);
            bundle = Bundle{"World Foundry", "Choose a game", {}};
            for (int i = 0; i < n; ++i)
                bundle.entries.push_back({i, i == longAt ? longName : "Level " + std::to_string(i + 1)});
            std::printf("SYNTHETIC %d\n", n);
        }
        else if (cmd == "autopick")
            std::printf("AUTO %d\n", AutoPick(bundle));
        else if (cmd == "menu")
        {
            int cursor = 0;
            std::string tv;
            in >> cursor >> tv;
            menu.reset(new Menu(bundle, cursor, tv == "tv" ? "D-pad choose - OK starts - Hold Back in a game for this menu"
                                                           : "Up/Down choose - Space starts - Backspace in a game comes back here"));
            State(*menu);
        }
        else if (cmd == "input" && menu)
        {
            std::string hex;
            long long ms = 0;
            in >> hex >> ms;
            menu->Update(uint32_t(std::stoul(hex, nullptr, 16)), ms);
            State(*menu);
        }
        else if (cmd == "rects" && menu)
        {
            int w = 0, h = 0;
            in >> w >> h;
            const bool changed = menu->Build(w, h, &rects);
            std::printf("RECTS %zu changed=%d\n", rects.size(), changed ? 1 : 0);
            for (const PhonepadRect& r : rects)
                std::printf("R %.2f %.2f %.2f %.2f %08x\n", r.x0, r.y0, r.x1, r.y1, unsigned(r.rgba));
        }
        else if (cmd == "row" && menu)
        {
            int i = 0;
            in >> i;
            std::printf("ROW %s\n", menu->RowText(i).c_str());
        }
        else if (cmd == "script")
        {
            std::string text, err;
            in >> text;
            if (script.Parse(text, &err))
                std::printf("SCRIPT ok %zu\n", script.Left());
            else
                std::printf("SCRIPT error %s\n", err.c_str());
        }
        else if (cmd == "next")
        {
            ScriptFrame f;
            if (script.Next(&f))
                std::printf("FRAME %x back=%d quit=%d\n", unsigned(f.buttons), f.back ? 1 : 0, f.quit ? 1 : 0);
            else
                std::printf("FRAME end\n");
        }
        else if (cmd == "quit")
            break;
        else
            std::printf("ERROR unknown command: %s\n", line.c_str());
    }
    return 0;
}

#endif  // WF_LEVEL_MENU_HOST
