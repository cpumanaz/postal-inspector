FROM alpine:3.19

RUN apk add --no-cache \
    fetchmail \
    ca-certificates \
    coreutils \
    && rm -rf /var/cache/apk/*

# Create vmail user/group matching Dovecot's vmail
RUN addgroup -g 5000 vmail && \
    adduser -D -u 5000 -G vmail -h /var/mail vmail

# Copy scripts
COPY entrypoint.sh /entrypoint.sh
COPY deliver.sh /usr/local/bin/deliver.sh
RUN chmod 755 /entrypoint.sh /usr/local/bin/deliver.sh

ENTRYPOINT ["/entrypoint.sh"]
