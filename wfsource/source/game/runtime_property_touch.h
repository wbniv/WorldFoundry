#pragma once
#include "runtime_property_ui.h"

namespace propertyui {
enum class TouchPhase { Down, Move, Up, Cancel };
struct TouchRect { float x0=0,y0=0,x1=0,y1=0; bool contains(float x,float y) const {return x>=x0&&x<x1&&y>=y0&&y<y1;} };
void touchConfigure(bool enabled,float density);
void touchInsets(int topPixels,int bottomPixels);
bool touchEnabled();
void touchReset();
TouchRect touchEntryRect(int width,int height);
// Returns true when the event belongs to the settings UI or its entry button.
bool touchEvent(TouchPhase phase,int pointer,float x,float y,int width,int height);
// Returns false only for Pick in 3D, whose scene overlay remains the existing renderer.
bool buildTouchHost(int width,int height,std::vector<PhonepadRect>& rects,std::vector<bitmaptext::Quad>* glyphs);
}
