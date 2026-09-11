#pragma once

#include "atom_sdk/core/models.hpp"

namespace atom::sdk {

DecodedResponse decode_json_response(const HttpResponse& response);
DecodedResponse decode_payload(const HttpResponse& response);

}  // namespace atom::sdk
