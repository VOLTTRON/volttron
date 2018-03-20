echo Issuing EiReport request to VEN with xml/$1.xml
curl -X POST -d @xml/$1.xml \
    --header "Content-Type:application/xml" \
    -v \
    http://127.0.0.1:8080/OpenADR2/Simple/2.0b/EiReport
