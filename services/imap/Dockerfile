FROM alpine:3.19

RUN apk add --no-cache \
    dovecot \
    dovecot-lmtpd \
    dovecot-pigeonhole-plugin \
    shadow \
    && rm -rf /var/cache/apk/*

# Create mail directory
RUN mkdir -p /var/mail && chmod 777 /var/mail

# Create sieve directory
RUN mkdir -p /etc/dovecot/sieve

# Copy main config
COPY dovecot.conf /etc/dovecot/dovecot.conf

# Copy sieve filter template (compiled at runtime from ALIAS_PREFIX)
COPY sieve/ /etc/dovecot/sieve/

# Create entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 143 993 24

ENTRYPOINT ["/entrypoint.sh"]
CMD ["dovecot", "-F"]
