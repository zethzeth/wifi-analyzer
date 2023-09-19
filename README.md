# Wifi analyzer

A program for testing the wifi-connection.

## Todo

- Make it possible to spot, if one is jumping between 2.4ghz and 5.0ghz, by logging the channel from airport somewhere. 
- Make mini speedtest to run with each test
- Make better formatted print, for table-like items (add_log_to_db print)
- Get Noise from airport, as well as Signal and SNR.
- Make a good overview. A good report.
- Consider 2.4g and 5g
- Make Trello board? 
- Save router information.
- Something regarding time of day? Must be relative to amount of Netflix and devices on network. 
- Add assumption before tests are done? 
- Add an 'overall quality of test'. Aggregated information of all results. Average? 
- Add a summary and put it in summary-table (new). Average local pings, average remote pings, Amount of timeouts, etc.
- Look into 'latency'
- Look into round trips for tests
- Look into 'pipe girth' and 'fluid speed' of a tests. What can be measured. 
- Look into comparing DNS-resolving times. Can it be added to the same test? 

## Setup

**Step 1: .env**

Correct values in `.env`

**Step 2: Venv**

Read the "Venv"-section of the Makefile.

## Useful commands

```
#  Trace the dig
dig +trace google.com
```

...Is it resolving the IP in the router? 


```
# Wi-Fi info
/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I

# Ping and traceroute
ping 8.8.8.8
traceroute 8.8.8.8
```

## Applications and tools

A list of applications I use.

### iAnalyzeWifi

Price: 59 DKK
Not worth premium. Don't buy.
Platform: Mac


### LanScan

Good for finding devices on network.
Not worth premium. Don't buy.
Platform: Mac

### Ultra Wifi

Gives a good analysis. Plus signal history! 
Premium is worth it, I'd say. But get the lifetime option.
Platform: Mac

### iWifi

Seems good. 
Seems worth Premium. 
Untried
Platform: Mac

### MTR

Platform: Mac or Linux
Has to run with sudo, like: `sudo mtr 8.8.8.8`

Free and pretty interesting.


