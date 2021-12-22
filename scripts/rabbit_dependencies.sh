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

   if [[ "$DIST" == "8" ]]; then
       erlang_url='https://packagecloud.io/rabbitmq/erlang/el/8/$basearch'
       erlang_package_name='erlang-24.1-1.el8.x86_64'
   else
       printf "Invalid centos version. Centos 8 is the only compatible versions\n"
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

    echo "installing ERLANG"
    ${prefix} apt-get update
    ${prefix} apt-get install -y gnupg apt-transport-https -y
    ${prefix} apt-get purge -yf erlang*
    # Add the signing key
    ## Team RabbitMQ's main signing key
    curl -1sLf "https://keys.openpgp.org/vks/v1/by-fingerprint/0A9AF2115F4687BD29803A206B73A36E6026DFCA" | sudo gpg --dearmor | sudo tee /usr/share/keyrings/com.rabbitmq.team.gpg > /dev/null
    ## Cloudsmith: modern Erlang repository
    curl -1sLf https://dl.cloudsmith.io/public/rabbitmq/rabbitmq-erlang/gpg.E495BB49CC4BBE5B.key | sudo gpg --dearmor | sudo tee /usr/share/keyrings/io.cloudsmith.rabbitmq.E495BB49CC4BBE5B.gpg > /dev/null

    if [[ -f "/etc/apt/sources.list.d/rabbitmq-erlang.list" ]]; then
      echo "\n/etc/apt/sources.list.d/rabbitmq-erlang.list exists. renaming current file to rabbitmq-erlang.list.old\n"
      mv /etc/apt/sources.list.d/rabbitmq-erlang.list /etc/apt/sources.list.d/rabbitmq-erlang.list.old
      exit_on_error
    fi
    ## Add apt repositories maintained by Team RabbitMQ
    ${prefix} tee /etc/apt/sources.list.d/rabbitmq-erlang.list <<EOF
## Provides modern Erlang/OTP releases
##
deb [signed-by=/usr/share/keyrings/io.cloudsmith.rabbitmq.E495BB49CC4BBE5B.gpg] https://dl.cloudsmith.io/public/rabbitmq/rabbitmq-erlang/deb/$OS $DIST main
deb-src [signed-by=/usr/share/keyrings/io.cloudsmith.rabbitmq.E495BB49CC4BBE5B.gpg] https://dl.cloudsmith.io/public/rabbitmq/rabbitmq-erlang/deb/$OS $DIST main
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
    erlang_package_version="1:24.2-1"
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
