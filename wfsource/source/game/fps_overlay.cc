//=============================================================================
// fps_overlay.cc: shared diagnostic frame-rate overlay
// Copyright (c) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// This program is free software; you can redistribute it and/or
// modify it under the terms of the GNU General Public License
// Version 2 as published by the Free Software Foundation.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software
// Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
//=============================================================================
// Description: Cached number-only overlay of raw mailbox frame rate.
// Original Author: World Foundry Group
//=============================================================================

#include "fps_overlay.hp"

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <cmath>

namespace fpscounter
{
bool enabled = true;

int Overlay::Build(Scalar fps, int width, int height)
{
	Validate();
	char text[32];
	std::snprintf(text, sizeof(text), "%.1f", fps.AsFloat());
	if (width == _width && height == _height && !std::strcmp(text, _text))
	{
		Validate();
		return _count;
	}
	std::strcpy(_text, text);
	_width = width;
	_height = height;
	_count = 0;
	_glyphs.clear();
	if (width <= 0 || height <= 0) { Validate(); return _count; }

	// About the old size: Regular 28 on the 1080p canvas, with the same padding.
	const float scale = std::max(1.0f, std::min(float(width), float(height)) / 360.0f);
	const float pad = 1.5f * scale;
	const float right = float(width) * 0.97f;
	const float bottom = float(height) * 0.97f;
	wfui::Transform t;
	t.s = std::min(float(width) / 1920.0f, float(height) / 1080.0f);
	t.ox = right - pad;
	t.oy = bottom - pad;
	_glyphs.clear();
	wfui::TextBytes(_glyphs, 0, 0, wfui::Small, 0xFFFFFFFFu, text, std::strlen(text), wfui::Baseline, wfui::Right, t);
	assert(!_glyphs.empty());
	// The plate fits the glyphs actually drawn, padded equally on every side.
	float left = _glyphs[0].x0, top = _glyphs[0].y0, glyphRight = _glyphs[0].x1, glyphBottom = _glyphs[0].y1;
	for (const auto& g : _glyphs)
	{
		left = std::min(left, g.x0); top = std::min(top, g.y0);
		glyphRight = std::max(glyphRight, g.x1); glyphBottom = std::max(glyphBottom, g.y1);
	}
	// Shift the text by whole pixels so its ink, not its advance box, sits pad inside the corner.
	const float dx = std::floor(right - pad - glyphRight + 0.5f), dy = std::floor(bottom - pad - glyphBottom + 0.5f);
	for (auto& g : _glyphs) { g.x0 += dx; g.x1 += dx; g.y0 += dy; g.y1 += dy; }
	_rects[_count++] = {left + dx - pad, top + dy - pad, glyphRight + dx + pad, glyphBottom + dy + pad, 0x101820B0u};
	Validate();
	return _count;
}

void Overlay::Validate() const
{
	assert(_count >= 0 && _count <= 1);
	assert(_text[sizeof(_text) - 1] == 0);
}
}
