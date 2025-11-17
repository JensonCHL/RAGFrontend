@echo off
echo Checking Qdrant collection status...

curl -X GET ^
  "https://3e1cfc1c-d37b-4ccb-a069-003af0ff7d44.eu-west-2-0.aws.cloud.qdrant.io:443/collections/DataStreamLit" ^
  -H "api-key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.gAklWn7p5M5l0koOWDApFEzr6Y-fYc85EBKDmmsLE20"

echo.
echo Command executed. Check the response above for current configuration.
pause