#include "httplib.h"
#include <iostream>
#include <string>

// 连接超时时间：3 秒
#define HTTP_CONNECTION_TIMEOUT 3
// Read 超时时间 30秒
#define HTTP_READ_TIMEOUT 30
// write 超时时间 30秒
#define HTTP_WRITE_TIMEOUT 30

httplib::Result httpGet(std::string ip, std::string uri, int readTimeoutSeconds = HTTP_READ_TIMEOUT) {
    httplib::Client client(ip);
    client.set_connection_timeout(HTTP_CONNECTION_TIMEOUT, 0);
    client.set_read_timeout(readTimeoutSeconds, 0);
    client.set_write_timeout(HTTP_WRITE_TIMEOUT, 0);
    return client.Get(uri.c_str());
}

httplib::Result httpPost(std::string ip, std::string uri, int readTimeoutSeconds = HTTP_READ_TIMEOUT) {
    httplib::Client client(ip);
    client.set_connection_timeout(HTTP_CONNECTION_TIMEOUT, 0);
    client.set_read_timeout(readTimeoutSeconds, 0);
    client.set_write_timeout(HTTP_WRITE_TIMEOUT, 0);
    return client.Post(uri.c_str());
}

httplib::Result httpPost(std::string ip, std::string uri, std::string content, int readTimeoutSeconds = HTTP_READ_TIMEOUT) {
    httplib::Client client(ip);
    client.set_connection_timeout(HTTP_CONNECTION_TIMEOUT, 0);
    client.set_read_timeout(readTimeoutSeconds, 0);
    client.set_write_timeout(HTTP_WRITE_TIMEOUT, 0);
    return client.Post(uri.c_str(), content, "application/json");
}

httplib::Result httpPut(std::string ip, std::string uri, std::string content, int readTimeoutSeconds = HTTP_READ_TIMEOUT) {
    httplib::Client client(ip);
    client.set_connection_timeout(HTTP_CONNECTION_TIMEOUT, 0);
    client.set_read_timeout(readTimeoutSeconds, 0);
    client.set_write_timeout(HTTP_WRITE_TIMEOUT, 0);
    return client.Put(uri.c_str(), content, "application/json");
}

