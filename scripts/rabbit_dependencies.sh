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
baseurl=https://packages.erlang-solutions.com/rpm/centos/\$releasever/\$basearch
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
   ${prefix} yum install -y erlang-$erlang_package_version
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

    echo "Installing ERLANG"
    ${prefix} apt-get update
    ${prefix} apt-get install -y gnupg apt-transport-https -y
    ${prefix} apt-get purge -yf erlang-base
    # Add the signing key
    wget https://packages.erlang-solutions.com/ubuntu/erlang_solutions.asc
    sudo apt-key add erlang_solutions.asc
    rm erlang_solutions.asc
    if [[ -f "/etc/apt/sources.list.d/erlang.list" ]]; then
      echo "\n/etc/apt/sources.list.d/erlang.list exists. renaming current file to erlang.list.old\n"
      ${prefix} mv /etc/apt/sources.list.d/erlang.list /etc/apt/sources.list.d/erlang.list.old
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
        erlang-base=$version\
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
    ${prefix} apt-get install -y --allow-downgrades ${to_install}
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
    erlang_package_version="1:24.1.7-1"
    is_arm="FALSE"
    install_on_debian
elif [[ "$os_name" == "centos" ]]; then
    erlang_package_version="24.2-1.el8"
    install_on_centos
else
    printf "For operating system/distributions not supported by this script, please refer to https://www.rabbitmq.com/which-erlang.html#erlang-repositories\n"
    print_usage
fi

echo "Finished installing dependencies for rabbitmq"
