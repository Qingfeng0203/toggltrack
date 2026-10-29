// Copyright 2015 Toggl Desktop developers.

#ifndef SRC_URLS_H_
#define SRC_URLS_H_

#include <string>

namespace toggl {

namespace urls {

std::string Main();
std::string API();
std::string SyncAPI();
std::string TimelineUpload();
std::string WebSocket();

void SetUseStagingAsBackend(const bool value);

bool IsUsingStagingAsBackend();

// Custom backend base URL (for example "http://10.104.2.133:8080").
// When set to a non-empty value every backend host below resolves to it,
// so the desktop app talks to a self-hosted server instead of Toggl Cloud.
// An empty value restores the built-in hosts. Trailing slashes are stripped.

std::string CustomServerURL();

void SetCustomServerURL(const std::string &value);

bool HasCustomServerURL();

// Optional mirror endpoint. When set, every time entry that was pushed to
// the backend is also sent (best effort, fire and forget) to this base URL
// under POST /v1/time_entries. The main sync flow is not affected at all,
// so a broken mirror never blocks the user's normal work.

std::string MirrorURL();

void SetMirrorURL(const std::string &value);

bool HasMirrorURL();

bool RequestsAllowed();

void SetRequestsAllowed(const bool value);

bool ImATeapot();

void SetImATeapot(const bool value);

}  // namespace urls

}  // namespace toggl

#endif  // SRC_URLS_H_
