#ifndef WF_LIFETIME_GL_HPP
#define WF_LIFETIME_GL_HPP
// Include AFTER GL headers. Wrappers call the real GL entry points before the
// macro redirects below; production builds do not define any redirects.
#include <wf_lifetime.hpp>
#ifdef WF_LIFETIME_DIAGNOSTICS
namespace wflifetime_gl {
// The GL driver owns its internal C++ allocations. Do not attribute those to
// the calling level; explicit GPU handle records are made AFTER this scope.
template<class F> inline auto driver(F call)->decltype(call()){
    wflifetime::Scope external(0);return call();
}
enum Class { Buffer, Texture, VertexArray, Shader, Program, Fence, Classes };
inline const void* domain(Class c){static char keys[Classes];return &keys[c];}
inline const char* label(Class c){static const char* names[]={"GL buffer","GL texture","GL vertex array","GL shader","GL program","GL fence"};return names[c];}
inline void created(Class c,std::uintptr_t id){wflifetime::Scope objectOwner(wflifetime::current()?wflifetime::current():wflifetime::Persistent);wflifetime::acquire(wflifetime::Kind::Graphics,domain(c),id,0,label(c),__FILE__,__LINE__);}
inline void deleted(Class c,std::uintptr_t id){wflifetime::release(wflifetime::Kind::Graphics,domain(c),id);}
inline void contextLost(){for(int c=0;c<Classes;++c)wflifetime::discardGraphics(domain(Class(c)));}
inline void GenBuffers(GLsizei n,GLuint* ids){driver([&](){glGenBuffers(n,ids);});for(GLsizei i=0;i<n;++i)created(Buffer,ids[i]);}
inline void DeleteBuffers(GLsizei n,const GLuint* ids){driver([&](){glDeleteBuffers(n,ids);});for(GLsizei i=0;i<n;++i)deleted(Buffer,ids[i]);}
inline void GenTextures(GLsizei n,GLuint* ids){driver([&](){glGenTextures(n,ids);});for(GLsizei i=0;i<n;++i)created(Texture,ids[i]);}
inline void DeleteTextures(GLsizei n,const GLuint* ids){driver([&](){glDeleteTextures(n,ids);});for(GLsizei i=0;i<n;++i)deleted(Texture,ids[i]);}
inline void GenVertexArrays(GLsizei n,GLuint* ids){driver([&](){glGenVertexArrays(n,ids);});for(GLsizei i=0;i<n;++i)created(VertexArray,ids[i]);}
inline void DeleteVertexArrays(GLsizei n,const GLuint* ids){driver([&](){glDeleteVertexArrays(n,ids);});for(GLsizei i=0;i<n;++i)deleted(VertexArray,ids[i]);}
inline GLuint CreateShader(GLenum type){wflifetime::Scope scope(wflifetime::Persistent);GLuint id=driver([&](){return glCreateShader(type);});created(Shader,id);return id;}
inline void DeleteShader(GLuint id){driver([&](){glDeleteShader(id);});deleted(Shader,id);}
inline GLuint CreateProgram(){wflifetime::Scope scope(wflifetime::Persistent);GLuint id=driver([&](){return glCreateProgram();});created(Program,id);return id;}
inline void DeleteProgram(GLuint id){driver([&](){glDeleteProgram(id);});deleted(Program,id);}
inline GLsync FenceSync(GLenum condition,GLbitfield flags){wflifetime::Scope cache(wflifetime::Persistent);GLsync id=driver([&](){return glFenceSync(condition,flags);});created(Fence,reinterpret_cast<std::uintptr_t>(id));return id;}
inline void DeleteSync(GLsync id){driver([&](){glDeleteSync(id);});deleted(Fence,reinterpret_cast<std::uintptr_t>(id));}
inline void BufferData(GLenum target,GLsizeiptr size,const void* data,GLenum usage){
    driver([&](){glBufferData(target,size,data,usage);});GLint id=0;
    if(target==GL_ARRAY_BUFFER)glGetIntegerv(GL_ARRAY_BUFFER_BINDING,&id);
    else if(target==GL_ELEMENT_ARRAY_BUFFER)glGetIntegerv(GL_ELEMENT_ARRAY_BUFFER_BINDING,&id);
    if(id&&size>=0)wflifetime::resize(wflifetime::Kind::Graphics,domain(Buffer),std::uintptr_t(id),std::size_t(size));
}
}
#undef glGenBuffers
#define glGenBuffers wflifetime_gl::GenBuffers
#undef glDeleteBuffers
#define glDeleteBuffers wflifetime_gl::DeleteBuffers
#undef glGenTextures
#define glGenTextures wflifetime_gl::GenTextures
#undef glDeleteTextures
#define glDeleteTextures wflifetime_gl::DeleteTextures
#undef glGenVertexArrays
#define glGenVertexArrays wflifetime_gl::GenVertexArrays
#undef glDeleteVertexArrays
#define glDeleteVertexArrays wflifetime_gl::DeleteVertexArrays
#undef glCreateShader
#define glCreateShader wflifetime_gl::CreateShader
#undef glDeleteShader
#define glDeleteShader wflifetime_gl::DeleteShader
#undef glCreateProgram
#define glCreateProgram wflifetime_gl::CreateProgram
#undef glDeleteProgram
#define glDeleteProgram wflifetime_gl::DeleteProgram
#undef glFenceSync
#define glFenceSync wflifetime_gl::FenceSync
#undef glDeleteSync
#define glDeleteSync wflifetime_gl::DeleteSync
#undef glBufferData
#define glBufferData wflifetime_gl::BufferData

// Remaining GL entry points only cross the driver ownership boundary.
#undef glActiveTexture
#define glActiveTexture(...) wflifetime_gl::driver([&](){return glActiveTexture(__VA_ARGS__);})
#undef glAttachShader
#define glAttachShader(...) wflifetime_gl::driver([&](){return glAttachShader(__VA_ARGS__);})
#undef glBindBuffer
#define glBindBuffer(...) wflifetime_gl::driver([&](){return glBindBuffer(__VA_ARGS__);})
#undef glBindTexture
#define glBindTexture(...) wflifetime_gl::driver([&](){return glBindTexture(__VA_ARGS__);})
#undef glBindVertexArray
#define glBindVertexArray(...) wflifetime_gl::driver([&](){return glBindVertexArray(__VA_ARGS__);})
#undef glBlendFunc
#define glBlendFunc(...) wflifetime_gl::driver([&](){return glBlendFunc(__VA_ARGS__);})
#undef glBlendFuncSeparate
#define glBlendFuncSeparate(...) wflifetime_gl::driver([&](){return glBlendFuncSeparate(__VA_ARGS__);})
#undef glBufferSubData
#define glBufferSubData(...) wflifetime_gl::driver([&](){return glBufferSubData(__VA_ARGS__);})
#undef glClientWaitSync
#define glClientWaitSync(...) wflifetime_gl::driver([&](){return glClientWaitSync(__VA_ARGS__);})
#undef glCompileShader
#define glCompileShader(...) wflifetime_gl::driver([&](){return glCompileShader(__VA_ARGS__);})
#undef glDepthMask
#define glDepthMask(...) wflifetime_gl::driver([&](){return glDepthMask(__VA_ARGS__);})
#undef glDetachShader
#define glDetachShader(...) wflifetime_gl::driver([&](){return glDetachShader(__VA_ARGS__);})
#undef glDisable
#define glDisable(...) wflifetime_gl::driver([&](){return glDisable(__VA_ARGS__);})
#undef glDisableVertexAttribArray
#define glDisableVertexAttribArray(...) wflifetime_gl::driver([&](){return glDisableVertexAttribArray(__VA_ARGS__);})
#undef glDrawArrays
#define glDrawArrays(...) wflifetime_gl::driver([&](){return glDrawArrays(__VA_ARGS__);})
#undef glDrawElements
#define glDrawElements(...) wflifetime_gl::driver([&](){return glDrawElements(__VA_ARGS__);})
#undef glEnable
#define glEnable(...) wflifetime_gl::driver([&](){return glEnable(__VA_ARGS__);})
#undef glEnableVertexAttribArray
#define glEnableVertexAttribArray(...) wflifetime_gl::driver([&](){return glEnableVertexAttribArray(__VA_ARGS__);})
#undef glGetBooleanv
#define glGetBooleanv(...) wflifetime_gl::driver([&](){return glGetBooleanv(__VA_ARGS__);})
#undef glGetError
#define glGetError(...) wflifetime_gl::driver([&](){return glGetError(__VA_ARGS__);})
#undef glGetIntegerv
#define glGetIntegerv(...) wflifetime_gl::driver([&](){return glGetIntegerv(__VA_ARGS__);})
#undef glGetProgramInfoLog
#define glGetProgramInfoLog(...) wflifetime_gl::driver([&](){return glGetProgramInfoLog(__VA_ARGS__);})
#undef glGetProgramiv
#define glGetProgramiv(...) wflifetime_gl::driver([&](){return glGetProgramiv(__VA_ARGS__);})
#undef glGetShaderInfoLog
#define glGetShaderInfoLog(...) wflifetime_gl::driver([&](){return glGetShaderInfoLog(__VA_ARGS__);})
#undef glGetShaderiv
#define glGetShaderiv(...) wflifetime_gl::driver([&](){return glGetShaderiv(__VA_ARGS__);})
#undef glGetUniformLocation
#define glGetUniformLocation(...) wflifetime_gl::driver([&](){return glGetUniformLocation(__VA_ARGS__);})
#undef glIsEnabled
#define glIsEnabled(...) wflifetime_gl::driver([&](){return glIsEnabled(__VA_ARGS__);})
#undef glLinkProgram
#define glLinkProgram(...) wflifetime_gl::driver([&](){return glLinkProgram(__VA_ARGS__);})
#undef glMapBufferRange
#define glMapBufferRange(...) wflifetime_gl::driver([&](){return glMapBufferRange(__VA_ARGS__);})
#undef glPixelStorei
#define glPixelStorei(...) wflifetime_gl::driver([&](){return glPixelStorei(__VA_ARGS__);})
#undef glShaderSource
#define glShaderSource(...) wflifetime_gl::driver([&](){return glShaderSource(__VA_ARGS__);})
#undef glTexImage2D
#define glTexImage2D(...) wflifetime_gl::driver([&](){return glTexImage2D(__VA_ARGS__);})
#undef glTexParameteri
#define glTexParameteri(...) wflifetime_gl::driver([&](){return glTexParameteri(__VA_ARGS__);})
#undef glTexSubImage2D
#define glTexSubImage2D(...) wflifetime_gl::driver([&](){return glTexSubImage2D(__VA_ARGS__);})
#undef glUniform1f
#define glUniform1f(...) wflifetime_gl::driver([&](){return glUniform1f(__VA_ARGS__);})
#undef glUniform1i
#define glUniform1i(...) wflifetime_gl::driver([&](){return glUniform1i(__VA_ARGS__);})
#undef glUniform2f
#define glUniform2f(...) wflifetime_gl::driver([&](){return glUniform2f(__VA_ARGS__);})
#undef glUniform3f
#define glUniform3f(...) wflifetime_gl::driver([&](){return glUniform3f(__VA_ARGS__);})
#undef glUniform3fv
#define glUniform3fv(...) wflifetime_gl::driver([&](){return glUniform3fv(__VA_ARGS__);})
#undef glUniformMatrix4fv
#define glUniformMatrix4fv(...) wflifetime_gl::driver([&](){return glUniformMatrix4fv(__VA_ARGS__);})
#undef glUnmapBuffer
#define glUnmapBuffer(...) wflifetime_gl::driver([&](){return glUnmapBuffer(__VA_ARGS__);})
#undef glUseProgram
#define glUseProgram(...) wflifetime_gl::driver([&](){return glUseProgram(__VA_ARGS__);})
#undef glVertexAttrib1f
#define glVertexAttrib1f(...) wflifetime_gl::driver([&](){return glVertexAttrib1f(__VA_ARGS__);})
#undef glVertexAttrib3f
#define glVertexAttrib3f(...) wflifetime_gl::driver([&](){return glVertexAttrib3f(__VA_ARGS__);})
#undef glVertexAttrib4f
#define glVertexAttrib4f(...) wflifetime_gl::driver([&](){return glVertexAttrib4f(__VA_ARGS__);})
#undef glVertexAttribPointer
#define glVertexAttribPointer(...) wflifetime_gl::driver([&](){return glVertexAttribPointer(__VA_ARGS__);})
#undef glViewport
#define glViewport(...) wflifetime_gl::driver([&](){return glViewport(__VA_ARGS__);})

// Surface and pixel-map GL calls can also trigger lazy driver work.
#undef glBegin
#define glBegin(...) wflifetime_gl::driver([&](){return glBegin(__VA_ARGS__);})
#undef glBindFramebuffer
#define glBindFramebuffer(...) wflifetime_gl::driver([&](){return glBindFramebuffer(__VA_ARGS__);})
#undef glBindRenderbuffer
#define glBindRenderbuffer(...) wflifetime_gl::driver([&](){return glBindRenderbuffer(__VA_ARGS__);})
#undef glBlitFramebuffer
#define glBlitFramebuffer(...) wflifetime_gl::driver([&](){return glBlitFramebuffer(__VA_ARGS__);})
#undef glCallList
#define glCallList(...) wflifetime_gl::driver([&](){return glCallList(__VA_ARGS__);})
#undef glCheckFramebufferStatus
#define glCheckFramebufferStatus(...) wflifetime_gl::driver([&](){return glCheckFramebufferStatus(__VA_ARGS__);})
#undef glClear
#define glClear(...) wflifetime_gl::driver([&](){return glClear(__VA_ARGS__);})
#undef glClearColor
#define glClearColor(...) wflifetime_gl::driver([&](){return glClearColor(__VA_ARGS__);})
#undef glColor3f
#define glColor3f(...) wflifetime_gl::driver([&](){return glColor3f(__VA_ARGS__);})
#undef glColor3ub
#define glColor3ub(...) wflifetime_gl::driver([&](){return glColor3ub(__VA_ARGS__);})
#undef glColor4ub
#define glColor4ub(...) wflifetime_gl::driver([&](){return glColor4ub(__VA_ARGS__);})
#undef glColorMaterial
#define glColorMaterial(...) wflifetime_gl::driver([&](){return glColorMaterial(__VA_ARGS__);})
#undef glEnd
#define glEnd(...) wflifetime_gl::driver([&](){return glEnd(__VA_ARGS__);})
#undef glFinish
#define glFinish(...) wflifetime_gl::driver([&](){return glFinish(__VA_ARGS__);})
#undef glFlush
#define glFlush(...) wflifetime_gl::driver([&](){return glFlush(__VA_ARGS__);})
#undef glFramebufferRenderbuffer
#define glFramebufferRenderbuffer(...) wflifetime_gl::driver([&](){return glFramebufferRenderbuffer(__VA_ARGS__);})
#undef glGenFramebuffers
#define glGenFramebuffers(...) wflifetime_gl::driver([&](){return glGenFramebuffers(__VA_ARGS__);})
#undef glGenRenderbuffers
#define glGenRenderbuffers(...) wflifetime_gl::driver([&](){return glGenRenderbuffers(__VA_ARGS__);})
#undef glLightModelf
#define glLightModelf(...) wflifetime_gl::driver([&](){return glLightModelf(__VA_ARGS__);})
#undef glLightfv
#define glLightfv(...) wflifetime_gl::driver([&](){return glLightfv(__VA_ARGS__);})
#undef glLoadIdentity
#define glLoadIdentity(...) wflifetime_gl::driver([&](){return glLoadIdentity(__VA_ARGS__);})
#undef glMaterialfv
#define glMaterialfv(...) wflifetime_gl::driver([&](){return glMaterialfv(__VA_ARGS__);})
#undef glMatrixMode
#define glMatrixMode(...) wflifetime_gl::driver([&](){return glMatrixMode(__VA_ARGS__);})
#undef glOrtho
#define glOrtho(...) wflifetime_gl::driver([&](){return glOrtho(__VA_ARGS__);})
#undef glPopAttrib
#define glPopAttrib(...) wflifetime_gl::driver([&](){return glPopAttrib(__VA_ARGS__);})
#undef glPopMatrix
#define glPopMatrix(...) wflifetime_gl::driver([&](){return glPopMatrix(__VA_ARGS__);})
#undef glPushAttrib
#define glPushAttrib(...) wflifetime_gl::driver([&](){return glPushAttrib(__VA_ARGS__);})
#undef glPushMatrix
#define glPushMatrix(...) wflifetime_gl::driver([&](){return glPushMatrix(__VA_ARGS__);})
#undef glReadPixels
#define glReadPixels(...) wflifetime_gl::driver([&](){return glReadPixels(__VA_ARGS__);})
#undef glRenderbufferStorage
#define glRenderbufferStorage(...) wflifetime_gl::driver([&](){return glRenderbufferStorage(__VA_ARGS__);})
#undef glRotatef
#define glRotatef(...) wflifetime_gl::driver([&](){return glRotatef(__VA_ARGS__);})
#undef glScissor
#define glScissor(...) wflifetime_gl::driver([&](){return glScissor(__VA_ARGS__);})
#undef glShadeModel
#define glShadeModel(...) wflifetime_gl::driver([&](){return glShadeModel(__VA_ARGS__);})
#undef glTexCoord2f
#define glTexCoord2f(...) wflifetime_gl::driver([&](){return glTexCoord2f(__VA_ARGS__);})
#undef glTranslatef
#define glTranslatef(...) wflifetime_gl::driver([&](){return glTranslatef(__VA_ARGS__);})
#undef glVertex2f
#define glVertex2f(...) wflifetime_gl::driver([&](){return glVertex2f(__VA_ARGS__);})
#undef glVertex2i
#define glVertex2i(...) wflifetime_gl::driver([&](){return glVertex2i(__VA_ARGS__);})
#undef glVertex3f
#define glVertex3f(...) wflifetime_gl::driver([&](){return glVertex3f(__VA_ARGS__);})
#undef glVertex4f
#define glVertex4f(...) wflifetime_gl::driver([&](){return glVertex4f(__VA_ARGS__);})
#endif
#endif
