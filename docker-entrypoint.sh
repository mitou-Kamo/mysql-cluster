#!/bin/bash
set -eo pipefail

# Preload jemalloc to avoid TLS allocation issues
export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2

# if command starts with an option, prepend mysqld
if [ "${1:0:1}" = '-' ]; then
    set -- mysqld "$@"
fi

# skip setup if they want an option that stops mysqld
wantHelp=
for arg; do
    case "$arg" in
        -'?'|--help|--print-defaults|-V|--version)
            wantHelp=1
            break
            ;;
    esac
done

_check_config() {
    toRun=( "$@" --verbose --help )
    if ! errors="$("${toRun[@]}" 2>&1 >/dev/null)"; then
        cat >&2 <<-EOM
ERROR: mysqld failed while attempting to check config
command was: "${toRun[*]}"

$errors
EOM
        exit 1
    fi
}

# Fetch value from server config
_get_config() {
    local conf="$1"; shift
    "$@" --verbose --help --log-bin-index="$(mktemp -u)" 2>/dev/null \
        | awk -v conf="$conf" '$1 == conf && /^[^ \t]/ { sub(/^[^ \t]+[ \t]+/, ""); print; exit }'
}

if [ "$1" = 'mysqld' ] && [ -z "$wantHelp" ]; then
    # Get config
    DATADIR="$(_get_config 'datadir' "$@")"

    if [ ! -d "$DATADIR/mysql" ]; then
        echo "Initializing database..."
        mkdir -p "$DATADIR"
        chown mysql:mysql "$DATADIR"

        "$@" --initialize-insecure --user=mysql --datadir="$DATADIR"

        # Start mysqld for initialization
        "$@" --user=mysql --skip-networking --socket=/var/run/mysqld/mysqld.sock &
        pid="$!"

        mysql=( mysql --protocol=socket -uroot -hlocalhost --socket=/var/run/mysqld/mysqld.sock )

        # Wait for mysqld to be ready
        for i in {30..0}; do
            if "${mysql[@]}" -e 'SELECT 1' &> /dev/null; then
                break
            fi
            echo 'MySQL init process in progress...'
            sleep 1
        done
        if [ "$i" = 0 ]; then
            echo 'MySQL init process failed.'
            exit 1
        fi

        # Set root password
        if [ -n "$MYSQL_ROOT_PASSWORD" ]; then
            "${mysql[@]}" <<-EOSQL
                ALTER USER 'root'@'localhost' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}' ;
                CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}' ;
                GRANT ALL ON *.* TO 'root'@'%' WITH GRANT OPTION ;
                FLUSH PRIVILEGES ;
EOSQL
        fi

        # Create database if specified
        if [ -n "$MYSQL_DATABASE" ]; then
            "${mysql[@]}" -p"$MYSQL_ROOT_PASSWORD" <<-EOSQL
                CREATE DATABASE IF NOT EXISTS \`$MYSQL_DATABASE\` ;
EOSQL
        fi

        # Create additional user if specified
        if [ -n "$MYSQL_USER" ] && [ -n "$MYSQL_PASSWORD" ]; then
            "${mysql[@]}" -p"$MYSQL_ROOT_PASSWORD" <<-EOSQL
                CREATE USER IF NOT EXISTS '$MYSQL_USER'@'%' IDENTIFIED BY '$MYSQL_PASSWORD' ;
EOSQL

            if [ -n "$MYSQL_DATABASE" ]; then
                "${mysql[@]}" -p"$MYSQL_ROOT_PASSWORD" <<-EOSQL
                    GRANT ALL ON \`$MYSQL_DATABASE\`.* TO '$MYSQL_USER'@'%' ;
                    FLUSH PRIVILEGES ;
EOSQL
            fi
        fi

        # Shutdown temporary server
        if ! kill -s TERM "$pid" || ! wait "$pid"; then
            echo 'MySQL init process failed.'
            exit 1
        fi

        echo 'MySQL init process done. Ready for start up.'
    fi

    chown -R mysql:mysql "$DATADIR"
fi

exec "$@"


