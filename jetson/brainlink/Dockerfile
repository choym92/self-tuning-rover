# rover-brainlink: the rover's one-way SSH tunnel to the LLM on the home Mac mini.
FROM alpine:3.20
RUN apk add --no-cache openssh-client
COPY link.sh /link.sh
ENTRYPOINT ["/bin/sh", "/link.sh"]
