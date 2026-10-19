#pragma once
// Android UI bridge only; callbacks queue results for the game thread.
#include <game/runtime_property_controls.h>
#include <jni.h>
#include <mutex>
namespace androidtext {
struct Result {uint64_t session=0;uint32_t field=0;std::string value;bool accept=false;};
inline std::mutex& mutex(){static std::mutex value;return value;}
inline std::vector<Result>& results(){static std::vector<Result> values;return values;}
inline void poll(){std::vector<Result> pending;{std::lock_guard<std::mutex> lock(mutex());pending.swap(results());}for(const auto& result:pending)propertyui::completeText(result.session,result.field,result.value,result.accept);}
inline jstring string(JNIEnv* env,const std::string& value){
 jclass cls=env->FindClass("java/lang/String");jmethodID constructor=env->GetMethodID(cls,"<init>","([BLjava/lang/String;)V");
 jbyteArray bytes=env->NewByteArray(value.size());env->SetByteArrayRegion(bytes,0,value.size(),reinterpret_cast<const jbyte*>(value.data()));jstring charset=env->NewStringUTF("UTF-8");
 auto text=static_cast<jstring>(env->NewObject(cls,constructor,bytes,charset));env->DeleteLocalRef(charset);env->DeleteLocalRef(bytes);env->DeleteLocalRef(cls);return text;
}
inline void install(ANativeActivity* activity){
 propertyui::textHost().show=[activity](const propertyui::TextRequest& request){
  JNIEnv* env=nullptr;bool attached=activity->vm->GetEnv(reinterpret_cast<void**>(&env),JNI_VERSION_1_6)!=JNI_OK;
  if(attached&&activity->vm->AttachCurrentThread(&env,nullptr)!=JNI_OK)return false;
  jclass cls=env->GetObjectClass(activity->clazz);jmethodID method=env->GetMethodID(cls,"showPropertyText","(JILjava/lang/String;Ljava/lang/String;II)V");bool ok=method!=nullptr;
  if(ok){jstring label=string(env,request.label),value=string(env,request.value);env->CallVoidMethod(activity->clazz,method,jlong(request.session),jint(request.field),label,value,jint(request.mode),jint(request.maxLength));env->DeleteLocalRef(label);env->DeleteLocalRef(value);}
  if(env->ExceptionCheck()){env->ExceptionClear();ok=false;}env->DeleteLocalRef(cls);if(attached)activity->vm->DetachCurrentThread();return ok;
 };
 propertyui::textHost().hide=[activity](uint64_t session){
  JNIEnv* env=nullptr;bool attached=activity->vm->GetEnv(reinterpret_cast<void**>(&env),JNI_VERSION_1_6)!=JNI_OK;
  if(attached&&activity->vm->AttachCurrentThread(&env,nullptr)!=JNI_OK)return;
  jclass cls=env->GetObjectClass(activity->clazz);jmethodID method=env->GetMethodID(cls,"dismissPropertyText","(J)V");if(method)env->CallVoidMethod(activity->clazz,method,jlong(session));
  if(env->ExceptionCheck())env->ExceptionClear();env->DeleteLocalRef(cls);if(attached)activity->vm->DetachCurrentThread();
 };
}
}
extern "C" JNIEXPORT void JNICALL Java_org_worldfoundry_wf_1game_WorldFoundryActivity_textResult(JNIEnv* env,jclass,jlong session,jint field,jbyteArray value,jboolean accept){
 if(!value)return;jsize length=env->GetArrayLength(value);if(length>65536)return;
 androidtext::Result result;result.session=uint64_t(session);result.field=uint32_t(field);result.accept=accept;result.value.resize(length);env->GetByteArrayRegion(value,0,length,reinterpret_cast<jbyte*>(&result.value[0]));
 std::lock_guard<std::mutex> lock(androidtext::mutex());if(androidtext::results().size()<16)androidtext::results().push_back(std::move(result));
}
