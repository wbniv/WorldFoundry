#pragma once
#include "../../../engine/runtime_property_host.hpp"
#include <hal/phonepad/phonepad_overlay.h>
#include "ui_font.hp"
namespace propertyui {
using FormInput=void(*)(wfprops::Form&,uint32_t);
FormInput& inputHandler();
void inputHost(uint32_t buttons);
// The settings editor, the object chooser and Pick in 3D (and planted::buildUI) as
// rectangles plus, when `glyphs` is given, their text as UI-font quads for wfui::Draw.
void buildHost(int w,int h,std::vector<PhonepadRect>& out,std::vector<bitmaptext::Quad>* glyphs=nullptr);
void build(wfprops::Form& editor,bool phone,int w,int h,std::vector<PhonepadRect>& out,std::vector<bitmaptext::Quad>* glyphs=nullptr);
// These screens' layout was drawn for the old stroke font: a text's y is the top of its capitals
// and `scale` is canvas pixels per font pixel. The UI font keeps that geometry: the text's
// middle goes where the old capitals' middle was (y + 3.5 * scale), in the variant the plan
// gives the scale (docs/plans/2026-10-17-settings-editor-font.md: title, body, small).
wfui::Variant variantFor(float scale);
float textWidth(float scale,const std::string& text);   // canvas pixels
// Appends `text` to `glyphs` on a 1920x1080 canvas scaled by (sx, sy); null `glyphs` draws nothing.
void drawText(std::vector<bitmaptext::Quad>* glyphs,float sx,float sy,float x,float y,float scale,const std::string& text,uint32_t color,wfui::Variant variant=wfui::VariantCount);}
