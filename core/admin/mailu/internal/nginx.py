from mailu import models
from flask import current_app as app

import re
import urllib.parse
import ipaddress
import socket
import tenacity
from socrate import system


SUPPORTED_AUTH_METHODS = ["none", "plain"]


STATUSES = {
    "authentication": ("Authentication credentials invalid", {
        "imap": "AUTHENTICATIONFAILED",
        "smtp": "535 5.7.8",
        "pop3": "-ERR Authentication failed"
    }),
}


def handle_authentication(headers):
    """ Handle an HTTP nginx authentication request
    See: http://nginx.org/en/docs/mail/ngx_mail_auth_http_module.html#protocol
    """
    method = headers["Auth-Method"]
    protocol = headers["Auth-Protocol"]
    # Incoming mail, no authentication
    if method == "none" and protocol == "smtp":
        server, port = get_server(headers["Auth-Protocol"], False)
        return {
            "Auth-Status": "OK",
            "Auth-Server": server,
            "Auth-Port": port
        }
    # Authenticated user
    elif method == "plain":
        server, port = get_server(headers["Auth-Protocol"], True)
        # According to RFC2616 section 3.7.1 and PEP 3333, HTTP headers should
        # be ASCII and are generally considered ISO8859-1. However when passing
        # the password, nginx does not transcode the input UTF string, thus
        # we need to manually decode.
        raw_user_email = urllib.parse.unquote(headers["Auth-User"])
        user_email = raw_user_email.encode("iso8859-1").decode("utf8")
        raw_password = urllib.parse.unquote(headers["Auth-Pass"])
        password = raw_password.encode("iso8859-1").decode("utf8")
        ip = urllib.parse.unquote(headers["Client-Ip"])
        user = models.User.query.get(user_email)
        status = False
        if user:
            for token in user.tokens:
                if (token.check_password(password) and
                    (not token.ip or token.ip == ip)):
                        status = True
            if user.check_password(password):
                status = True
            if status:
                if protocol == "imap" and not user.enable_imap:
                    status = False
                elif protocol == "pop3" and not user.enable_pop:
                    status = False
        if status and user.enabled:
            return {
                "Auth-Status": "OK",
                "Auth-Server": server,
                "Auth-Port": port
            }
        else:
            status, code = get_status(protocol, "authentication")
            return {
                "Auth-Status": status,
                "Auth-Error-Code": code,
                "Auth-Wait": 0
            }
    # Unexpected
    return {}


def get_status(protocol, status):
    """ Return the proper error code depending on the protocol
    """
    status, codes = STATUSES[status]
    return status, codes[protocol]

def extract_host_port(host_and_port, default_port):
    result = urllib.parse.urlsplit('//{}'.format(host_and_port))
    host, port = result.hostname, result.port
    return host, int(port) if port else default_port

def get_server(protocol, authenticated=False):
    if protocol == "imap":
        hostname, port = extract_host_port(app.config['IMAP_ADDRESS'], 143)
    elif protocol == "pop3":
        hostname, port = extract_host_port(app.config['POP3_ADDRESS'], 110)
    elif protocol == "smtp":
        if authenticated:
            # We make them the same because both cases, nginx does its job
            hostname, port = extract_host_port(app.config['SMTP_ADDRESS'], 10025)
        else:
            hostname, port = extract_host_port(app.config['SMTP_ADDRESS'], 25)
    try:
        # test if hostname is already resolved to an ip adddress
        ipaddress.ip_address(hostname)
    except:
        # hostname is not an ip address - so we need to resolve it
        hostname = system.resolve_address(hostname)
    return hostname, port