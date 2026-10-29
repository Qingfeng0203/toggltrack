// Copyright 2015 Toggl Desktop developers

#include "urls.h"

namespace toggl {

namespace urls {

// Whether requests are sent to staging backend

#ifndef TOGGL_PRODUCTION_BUILD
static bool use_staging_as_backend = true;
#else
static bool use_staging_as_backend = false;
#endif

// Whether requests are allowed to Toggl backend
static bool im_a_teapot_ = false;

// Whether requests are allowed at all (like in tests)
static bool requests_allowed_ = true;

// Self-hosted backend override, empty means "use the built-in hosts"
static std::string custom_server_url_ = "";

// Optional mirror for time entries pushed to the backend
static std::string mirror_url_ = "";

void SetUseStagingAsBackend(const bool value) {
    use_staging_as_backend = value;
}

bool IsUsingStagingAsBackend() {
    return use_staging_as_backend;
}

namespace {

std::string trim(const std::string &value) {
    const char *spaces = " \t\r\n";
    auto begin = value.find_first_not_of(spaces);
    if (begin == std::string::npos) {
        return "";
    }
    auto end = value.find_last_not_of(spaces);
    return value.substr(begin, end - begin + 1);
}

std::string normalizeBaseURL(const std::string &value) {
    std::string normalized = trim(value);

    // The app always appends an absolute path ("/push/...", "/api/v9/..."),
    // so the base must not end with a slash and must carry a scheme.
    while (normalized.size() > 0 && normalized[normalized.size() - 1] == '/') {
        normalized.erase(normalized.size() - 1);
    }

    if (!normalized.empty()
            && normalized.find("://") == std::string::npos) {
        normalized = "https://" + normalized;
    }

    return normalized;
}

}  // namespace

void SetCustomServerURL(const std::string &value) {
    custom_server_url_ = normalizeBaseURL(value);
}

void SetMirrorURL(const std::string &value) {
    mirror_url_ = normalizeBaseURL(value);
}

std::string MirrorURL() {
    return mirror_url_;
}

bool HasMirrorURL() {
    return !mirror_url_.empty();
}

std::string CustomServerURL() {
    return custom_server_url_;
}

bool HasCustomServerURL() {
    return !custom_server_url_.empty();
}

std::string Main() {
    if (HasCustomServerURL()) {
        return custom_server_url_;
    }
    if (use_staging_as_backend) {
        return "https://track.toggl.space";
    }
    return "https://track.toggl.com";
}

std::string API() {
    if (HasCustomServerURL()) {
        return custom_server_url_;
    }
    if (use_staging_as_backend) {
        return "https://desktop.track.toggl.space";
    }
    return "https://desktop.track.toggl.com";
}

std::string SyncAPI() {
    if (HasCustomServerURL()) {
        return custom_server_url_ + "/";
    }
    if (use_staging_as_backend) {
        return "https://sync.toggl.space/";
    }
    return "https://sync.toggl.com/";
}

std::string TimelineUpload() {
    if (HasCustomServerURL()) {
        return custom_server_url_;
    }
    if (use_staging_as_backend) {
        return "https://desktop.track.toggl.space";
    }
    return "https://desktop.track.toggl.com";
}

std::string WebSocket() {
    if (HasCustomServerURL()) {
        return custom_server_url_;
    }
    if (use_staging_as_backend) {
        return "https://desktop.track.toggl.space";
    }
    return "https://desktop.track.toggl.com";
}

bool ImATeapot() {
    return im_a_teapot_;
}

void SetImATeapot(const bool value) {
    im_a_teapot_ = value;
}

bool RequestsAllowed() {
    return requests_allowed_;
}

void SetRequestsAllowed(const bool value) {
    requests_allowed_ = value;
}


}  // namespace urls

}  // namespace toggl
