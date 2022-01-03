#!/usr/bin/env bash
set -e
ubuntu_list=(bionic focal)
list=(buster )
list=("${ubuntu_list[@]}" "${debian_list[@]}")
declare -A ubuntu_versions
ubuntu_versions=( ["ubuntu-18.04"]="bionic" ["ubuntu-20.04"]="focal")

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
<path>/rabbit_dependencies.sh <debian, or centos> <distribution name/ubuntu-<version> or centos version>
Valid Debian distributions: ${list[@]} ${!ubuntu_versions[@]}
Valid centos versions: 8
"
 exit 0

}


function install_on_centos {

   if [[ "$DIST" != "8" ]]; then
       printf "Invalid centos version. Centos 8 is the only compatible versions\n"
       print_usage
   fi

   repo="## In /etc/yum.repos.d/erlang.repo
[erlang-solutions]
name=CentOS $releasever - $basearch - Erlang Solutions
baseurl=https://packages.erlang-solutions.com/rpm/centos/$releasever/$basearch
gpgcheck=1
gpgkey=https://packages.erlang-solutions.com/rpm/erlang_solutions.asc
enabled=1
"
   if [[ -f "/etc/yum.repos.d/erlang.repo" ]]; then
      echo "\n/etc/yum.repos.d/erlang.repo exists. renaming current file to rlang.repo.old\n"
      mv /etc/yum.repos.d/erlang.repo /etc/yum.repos.d/erlang.repo.old
      exit_on_error
   fi
   echo "$repo" | ${prefix} tee -a /etc/yum.repos.d/erlang.repo
   rpm --import https://packages.erlang-solutions.com/rpm/erlang_solutions.asc
   version=${erlang_package_version}
   to_install="\
        erlang-asn1=$version \
        erlang-crypto=$version \
        erlang-eldap=$version \
        erlang-ftp=$version \
        erlang-inets=$version \
        erlang-mnesia=$version \
        erlang-os-mon=$version \
        erlang-parsetools=$version \
        erlang-public-key=$version \
        erlang-runtime-tools=$version \
        erlang-snmp=$version \
        erlang-ssl=$version \
        erlang-syntax-tools=$version \
        erlang-tools=$version \
        erlang-xmerl=$version \
        erlang-tftp=$version \
        "

   ${prefix} yum install -y ${to_install}
   exit_on_error
}

function install_on_debian {
    FOUND=0
    OS=""
    for item in "${ubuntu_list[@]}"; do
        if [[ "$DIST" == "$item" ]]; then
        FOUND=1
        OS="ubuntu"
        break
        fi
    done

    if [[ "$FOUND" != "1" ]]; then
        for item in "${debian_list[@]}"; do
            if [[ "$DIST" == "$item" ]]; then
            FOUND=1
            OS="debian"
            break
            fi
        done
    fi

    if [[ "$FOUND" != "1" ]]; then
        # check if ubuntu-version was passed if so map it to name
        for ubuntu_version in "${!ubuntu_versions[@]}"; do
            if [[ "$DIST" == "$ubuntu_version" ]]; then
                FOUND=1
                DIST="${ubuntu_versions[$ubuntu_version]}"
                OS="ubuntu"
                break
            fi
        done
    fi

    if [[ "$FOUND" != "1" ]]; then
        echo "Invalid distribution found"
        print_usage
    fi

    echo "**installing ERLANG"
    ${prefix} apt-get update
    echo "installing ERLANG 1"

    ${prefix} apt-get install -y gnupg apt-transport-https -y
    echo "installing ERLANG 2"

    ${prefix} apt-get purge -yf erlang*
    echo "AFTER PURGE"
    # Add the signing key
    echo "Before wget"
    wget https://packages.erlang-solutions.com/ubuntu/erlang_solutions.asc
    echo "after wget"
    sudo apt-key add erlang_solutions.asc
    echo "after import of gpg key"
    rm erlang_solutions.asc
    echo "after rm"
    if [[ -f "/etc/apt/sources.list.d/erlang.list" ]]; then
      echo "\n/etc/apt/sources.list.d/erlang.list exists. renaming current file to erlang.list.old\n"
      mv /etc/apt/sources.list.d/rabbitmq-erlang.list /etc/apt/sources.list.d/erlang.list.old
      exit_on_error
    fi
    ## Add apt repository
    ${prefix} tee /etc/apt/sources.list.d/erlang.list <<EOF
## Provides modern Erlang/OTP releases
##
deb https://packages.erlang-solutions.com/$OS $DIST contrib
EOF
    version=${erlang_package_version}
    to_install="\
        erlang-asn1=$version \
        erlang-crypto=$version \
        erlang-eldap=$version \
        erlang-ftp=$version \
        erlang-inets=$version \
        erlang-mnesia=$version \
        erlang-os-mon=$version \
        erlang-parsetools=$version \
        erlang-public-key=$version \
        erlang-runtime-tools=$version \
        erlang-snmp=$version \
        erlang-ssl=$version \
        erlang-syntax-tools=$version \
        erlang-tools=$version \
        erlang-xmerl=$version \
        erlang-tftp=$version \
        "

    ${prefix} apt-get update
    ${prefix} apt-get install -y ${to_install}
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
    erlang_package_version="1:24.1.5-1"
    is_arm="FALSE"
    install_on_debian
elif [[ "$os_name" == "centos" ]]; then
    install_on_centos
else
    printf "For operating system/distributions not supported by this script, please install Erlang manually with the \
following components- ssl, publickey, asn1, and crypto.\n"
    print_usage
fi

echo "Finished installing dependencies for rabbitmq"
