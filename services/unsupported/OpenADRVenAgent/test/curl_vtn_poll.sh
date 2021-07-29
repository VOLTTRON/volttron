echo Issuing EiPoll request to EPRI VTN server with xml/$1.xml
curl -X POST -d @xml/$1.xml \
    --header "Content-Type:application/xml" \
    -v \
    http://openadr-vtn.ki-evi.com:4447/OpenADR2/Simple/2.0b/OadrPoll
