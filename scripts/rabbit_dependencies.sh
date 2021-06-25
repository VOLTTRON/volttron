#!/usr/bin/env bash
set -e

list=( bionic buster )
declare -A ubuntu_versions
ubuntu_versions=( ["ubuntu-16.04"]="xenial" ["ubuntu-18.04"]="bionic" ["ubuntu-20.04"]="focal")

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
<path>/rabbit_dependencies.sh <debian, raspbian, or centos> <distribution name/ubuntu-<version> or centos version>
Valid Raspbian/Debian distributions: ${list[@]} ${!ubuntu_versions[@]}
Valid centos versions: 6, 7, 8
"
 exit 0

}


function install_on_centos {

   if [[ "$DIST" == "6" ]]; then
       erlang_url='https://packagecloud.io/rabbitmq/erlang/el/6/$basearch'
       erlang_package_name='erlang-21.3.8.21-1.el6.x86_64'
   elif [[ "$DIST" == "7" ]]; then
       erlang_url='https://packagecloud.io/rabbitmq/erlang/el/7/$basearch'
       erlang_package_name='erlang-21.3.8.21-1.el7.x86_64'
   elif [[ "$DIST" == "8" ]]; then
       erlang_url='https://packagecloud.io/rabbitmq/erlang/el/8/$basearch'
       erlang_package_name='erlang-21.3.8.21-1.el8.x86_64'
   else
       printf "Invalid centos version. 6, 7, and 8 are the only compatible versions\n"
       print_usage
   fi

   repo="## In /etc/yum.repos.d/rabbitmq-erlang.repo
[rabbitmq_erlang]
name=rabbitmq_erlang
baseurl=$erlang_url
repo_gpgcheck=1
gpgcheck=0
enabled=1
gpgkey=https://packagecloud.io/rabbitmq/erlang/gpgkey
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
metadata_expire=300
"
   if [[ -f "/etc/yum.repos.d/rabbitmq-erlang.repo" ]]; then
      echo "\n/etc/yum.repos.d/rabbitmq-erlang.repo exists. renaming current file to rabbitmq-erlang.repo.old\n"
      mv /etc/yum.repos.d/rabbitmq-erlang.repo /etc/yum.repos.d/rabbitmq-erlang.repo.old
      exit_on_error
   fi
   echo "$repo" | ${prefix} tee -a /etc/yum.repos.d/rabbitmq-erlang.repo
   ${prefix} yum install $erlang_package_name
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
        # check if ubuntu-version was passed if so map it to name
        for ubuntu_version in "${!ubuntu_versions[@]}"; do
            if [[ "$DIST" == "$ubuntu_version" ]]; then
                FOUND=1
                DIST="${ubuntu_versions[$ubuntu_version]}"
                break
            fi
        done
    fi

    if [[ "$FOUND" != "1" ]]; then
        echo "Invalid distribution found"
        print_usage
    fi

    echo "installing ERLANG"
    ${prefix} apt-get update
    if [[ "$DIST" == "xenial" ]] || [[ "$DIST" == "bionic" ]]; then
        ${prefix} apt-get install -y apt-transport-https libwxbase3.0-0v5 libwxgtk3.0-0v5 libsctp1  build-essential python-dev openssl libssl-dev libevent-dev git
    else
        ${prefix} apt-get install -y apt-transport-https libwxbase3.0-0v5 libwxgtk3.0-gtk3-0v5 libsctp1  build-essential python-dev openssl libssl-dev libevent-dev git
    fi
    set +e
    ${prefix} apt-get purge -yf erlang*
    set -e
    # Add the signing key
    wget -O- https://packages.erlang-solutions.com/ubuntu/erlang_solutions.asc | ${prefix} apt-key add -

    if [[ ! -f "/etc/apt/sources.list.d/erlang.solutions.list" ]]; then
        echo "deb https://packages.erlang-solutions.com/ubuntu $DIST contrib" | ${prefix} tee /etc/apt/sources.list.d/erlang.solutions.list
    fi

    version=${erlang_package_version}
    common_deb_pkgs="\
        erlang-asn1=$version \
        erlang-base=$version \
        erlang-crypto=$version \
        erlang-diameter=$version \
        erlang-edoc=$version \
        erlang-eldap=$version \
        erlang-erl-docgen=$version \
        erlang-eunit=$version \
        erlang-inets=$version \
        erlang-mnesia=$version \
        erlang-odbc=$version \
        erlang-os-mon=$version \
        erlang-parsetools=$version \
        erlang-public-key=$version \
        erlang-runtime-tools=$version \
        erlang-snmp=$version \
        erlang-ssh=$version \
        erlang-ssl=$version \
        erlang-syntax-tools=$version \
        erlang-tools=$version \
        erlang-xmerl=$version \
        "
    x86_pkgs="\
        erlang-ic=$version \
        erlang-inviso=$version \
        erlang-percept=$version \
        "
    to_install=""
    if [[ $is_arm == "FALSE" ]]; then
       to_install="${common_deb_pkgs} ${x86_pkgs}"
    else
       to_install="${common_deb_pkgs}"
    fi

    ${prefix} apt-get update
    ${prefix} apt-get install -yf
    ${prefix} apt-get install -y ${to_install}
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
is_arm="FALSE"

${prefix} pwd > /dev/null

if [[ "$os_name" == "debian" ]]; then
    erlang_package_version="1:22.1.8.1-1"
    is_arm="FALSE"
    install_on_debian
elif [[ "$os_name" == "raspbian" ]]; then
    erlang_package_version="1:21.2.6+dfsg-1"
    is_arm="TRUE"
    install_on_debian
elif [[ "$os_name" == "centos" ]]; then
    install_on_centos
else
    printf "For operating system/distributions not supported by this script, please install Erlang manually with the \
following components- ssl, publickey, asn1, and crypto.\n"
    print_usage
fi

echo "Finished installing dependencies for rabbitmq"
