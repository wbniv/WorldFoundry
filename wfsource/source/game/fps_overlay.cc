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
#include "../../../engine/vendor/stb_easy_font.h"

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
	if (width <= 0 || height <= 0) { Validate(); return _count; }

	const float scale = std::max(1.0f, std::min(float(width), float(height)) / 360.0f);
	const float pad = 3.0f * scale;
	const float right = float(width) * 0.97f;
	const float bottom = float(height) * 0.97f;
	const float x = right - pad - stb_easy_font_width(text) * scale;
	const float y = bottom - pad - 12.0f * scale;
	_rects[_count++] = {x - pad, y - pad, right, bottom, 0x101820B0u};

	// stb writes float positions: retain float alignment on 32-bit ARM.
	float vertices[MAX_QUADS * 16];
	const int count = stb_easy_font_print(0, 0, text, NULL, vertices, sizeof(vertices));
	for (int i = 0; i < count; ++i)
	{
		const float* v = vertices + i * 16;
		_rects[_count++] = {x + v[0] * scale, y + v[1] * scale,
							x + v[8] * scale, y + v[9] * scale, 0xFFFFFFFFu};
	}
	Validate();
	return _count;
}

void Overlay::Validate() const
{
	assert(_count >= 0 && _count <= MAX_QUADS + 1);
	assert(_text[sizeof(_text) - 1] == 0);
}
}
