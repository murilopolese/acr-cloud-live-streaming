# ACR Cloud live stream fingerprinting tool

This tool extracts fingerprints of live channels and upload them into your bucket in realtime.

- Before using this tool, you must register on our platform and log into your dashboard.
- Sign up now for a free 14 day trial: http://console.acrcloud.com/signup
- Create a "Live Channel" bucket and add the url of your streams into it.
- Then, create a "Live Channel Detection" project and attach the bucket which contains your chosen stream urls.
- Save the "access_key" and "access_secret" of the project which you have created.
- Update the file `lib/client.conf` with your "access_key" and "access_secret"


## Run/Build the docker container

```bash
docker build -t acrcloud .
docker run acrcloud
```

## TODO

Use environment variables instead of hardcoded configuration on `lib/client.conf`
