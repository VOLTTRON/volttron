#!/usr/bin/env bash
list=( bionic  artful stretch buster trusty xenial )

function exit_on_error {
    rc=$?
    if [[ $rc != 0 ]]
    then
        printf "\n## Script could not complete successfully because of above error## \n"
        exit $rc
    fi

}

function print_usage {
 echo "
Command Usage:
<path>/rabbit_dependencies.sh <debian or centos> <distribution name or centos version>
Valid Debian distributions: ${list[@]}
Valid centos versions: 6, 7, 8
"
 exit 0

}


function install_on_centos {

   if [[ "$DIST" == "6" ]]; then
       erlang_url='https://dl.bintray.com/rabbitmq-erlang/rpm/erlang/21/el/6'
   elif [[ "$DIST" == "7" ]]; then
       erlang_url='https://dl.bintray.com/rabbitmq-erlang/rpm/erlang/21/el/7'
   elif [[ "$DIST" == "8" ]]; then
       erlang_url='https://dl.bintray.com/rabbitmq-erlang/rpm/erlang/21/el/8'
   else
       printf "Invalid centos version. 6, 7, and 8 are the only compatible versions\n"
       print_usage
   fi

   repo="## In /etc/yum.repos.d/rabbitmq-erlang.repo
[rabbitmq-erlang]
name=rabbitmq-erlang
baseurl=$erlang_url
gpgcheck=1
gpgkey=https://dl.bintray.com/rabbitmq/Keys/rabbitmq-release-signing-key.asc
repo_gpgcheck=0
enabled=1"

    if [[ ! -f "/etc/yum.repos.d/rabbitmq-erlang.repo" ]]; then
      echo "$repo" | ${prefix} tee -a /etc/yum.repos.d/rabbitmq-erlang.repo
      exit_on_error
    else
      echo "\nrepo file /etc/yum.repos.d/rabbitmq-erlang.repo already exists\n"
    fi
    ${prefix} yum install erlang
    exit_on_error
}

function install_on_debian {
    FOUND=0
    for item in ${list[@]}; do
        if [[ "$DIST" == "$item" ]]; then
        FOUND=1
        break
        fi
    done

    if [[ "$FOUND" != "1" ]]; then
        echo "Invalid distribution found"
        print_usage
    fi

    echo "installing ERLANG"
    ${prefix} apt-get install apt-transport-https libwxbase3.0-0v5 libwxgtk3.0-0v5 libsctp1  build-essential python-dev openssl libssl-dev libevent-dev git
    ${prefix} apt-get purge -yf erlang*
    # Add the signing key
    wget -O- https://packages.erlang-solutions.com/ubuntu/erlang_solutions.asc | ${prefix} apt-key add -

    if [[ ! -f "/etc/apt/sources.list.d/erlang.solutions.list" ]]; then
        echo "deb https://packages.erlang-solutions.com/ubuntu $DIST contrib" | ${prefix} tee /etc/apt/sources.list.d/erlang.solutions.list
    fi

    version=${erlang_package_version}
    ${prefix} apt-get update
    ${prefix} apt-get install -yf
    ${prefix} apt-get install -y "erlang-asn1=$version" \
        "erlang-base=$version" \
        "erlang-crypto=$version" \
        "erlang-diameter=$version" \
        "erlang-edoc=$version" \
        "erlang-eldap=$version" \
        "erlang-erl-docgen=$version" \
        "erlang-eunit=$version" \
        "erlang-ic=$version" \
        "erlang-inets=$version" \
        "erlang-inviso=$version" \
        "erlang-mnesia=$version" \
        "erlang-odbc=$version" \
        "erlang-os-mon=$version" \
        "erlang-parsetools=$version" \
        "erlang-percept=$version" \
        "erlang-public-key=$version" \
        "erlang-runtime-tools=$version" \
        "erlang-snmp=$version" \
        "erlang-ssh=$version" \
        "erlang-ssl=$version" \
        "erlang-syntax-tools=$version" \
        "erlang-tools=$version" \
        "erlang-xmerl=$version"

    ${prefix} apt-get install -y "erlang-nox=$version"
}

os_name="$1"
DIST="$2"
user=`whoami`
if [[ ${user} == 'root' ]]; then
  prefix=""
else
  prefix="sudo"
fi

${prefix} pwd > /dev/null

if [[ "$os_name" == "debian" ]]; then
    erlang_package_version="1:22.1.8.1-1"
    install_on_debian
elif [[ "$os_name" == "raspbian" ]]; then
    erlang_package_version="1:21.2.6+dfsg-1"
    install_on_debian
elif [[ "$os_name" == "centos" ]]; then
    install_on_centos
else
    printf "For operating system/distributions not supported by this script, please install Erlang manually with the \
following components- ssl, publickey, asn1, and crypto.\n"
    print_usage
fi

echo "Finished installing dependencies for rabbitmq"
