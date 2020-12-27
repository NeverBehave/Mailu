#ARG DISTRO=alpine:3.12
ARG DISTRO=ubuntu:20.04
# This is because alpine musl dns resolver's problem
FROM $DISTRO
# python3 shared with most images
ENV DEBIAN_FRONTEND noninteractive

RUN set -x; \
	apt-get -q update && \
	apt-get -qy upgrade && \
	apt-get -qy --no-install-recommends install \
    python3 git bash python3-pip \
  && pip3 install --upgrade pip

# Shared layer between nginx, dovecot, postfix, postgresql, rspamd, unbound, rainloop, roundcube
RUN pip3 install git+git://github.com/NeverBehave/socrate.git multidict

# Image specific layers under this line
RUN apt-get -qy --no-install-recommends install rspamd ca-certificates curl

RUN mkdir /run/rspamd

COPY conf/ /conf
COPY start.py /start.py

EXPOSE 11332/tcp 11334/tcp 11335/tcp

VOLUME ["/var/lib/rspamd"]

CMD /start.py

HEALTHCHECK --start-period=350s CMD curl -f -L http://localhost:11334/ || exit 1
