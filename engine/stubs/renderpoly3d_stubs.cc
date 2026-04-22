//==============================================================================
// renderpoly3d_stubs.cc — iOS-only Phase 2B2 link stubs
//
// The 8 RenderObject3D::RenderPoly3D* methods normally live in
// gfx/glpipeline/rend{f,g}{c,t}{l,p}.cc (one per material type) and call
// into the GL backend. All of gfx/glpipeline is excluded from the iOS
// build since it hard-depends on GLES; Material::Get3DRenderObjectPtr
// still takes addresses of those methods to build its dispatch table,
// which forces the link to resolve them.
//
// These no-op stubs satisfy the linker for Phase 2B2 (compile-and-link
// the engine on iOS). Phase 2B3 lands backend_metal.mm and real Metal
// impls replace these stubs.
//==============================================================================

#if defined(WF_TARGET_IOS)

#include <gfx/rendobj3.hp>

int RenderObject3D::RenderPoly3DFlatColorLit(Primitive*)          { return 0; }
int RenderObject3D::RenderPoly3DGouraudColorLit(Primitive*)       { return 0; }
int RenderObject3D::RenderPoly3DFlatTextureLit(Primitive*)        { return 0; }
int RenderObject3D::RenderPoly3DGouraudTextureLit(Primitive*)     { return 0; }
int RenderObject3D::RenderPoly3DFlatColorPreLit(Primitive*)       { return 0; }
int RenderObject3D::RenderPoly3DGouraudColorPreLit(Primitive*)    { return 0; }
int RenderObject3D::RenderPoly3DFlatTexturePreLit(Primitive*)     { return 0; }
int RenderObject3D::RenderPoly3DGouraudTexturePreLit(Primitive*)  { return 0; }

#endif
