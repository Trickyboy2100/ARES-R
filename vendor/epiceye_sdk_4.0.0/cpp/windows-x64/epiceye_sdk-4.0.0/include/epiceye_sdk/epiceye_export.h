#ifndef TFTECH_EPICEYESDK_EXPORT_H
#define TFTECH_EPICEYESDK_EXPORT_H

#if defined(_WIN32) && defined(EPICEYE_SDK_SHARED)
#if defined(EPICEYE_SDK_BUILDING)
#define EPICEYE_SDK_API __declspec(dllexport)
#else
#define EPICEYE_SDK_API __declspec(dllimport)
#endif
#else
#define EPICEYE_SDK_API
#endif

#endif
