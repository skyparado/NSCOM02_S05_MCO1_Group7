from socket import *
import os
import sys
import struct
import time
import select
import binascii

ICMP_ECHO_REQUEST = 8

def checksum(string):
    csum = 0
    countTo = (len(string) // 2) * 2
    count = 0
    while count < countTo:
        thisVal = string[count+1] * 256 + string[count]
        csum = csum + thisVal
        csum = csum & 0xffffffff
        count = count + 2
    if countTo < len(string):
        csum = csum + string[len(string) - 1]
        csum = csum & 0xffffffff
    csum = (csum >> 16) + (csum & 0xffff)
    csum = csum + (csum >> 16)
    answer = ~csum
    answer = answer & 0xffff
    answer = answer >> 8 | (answer << 8 & 0xff00)
    return answer

def receiveOnePing(mySocket, ID, seq, timeout, destAddr):
    timeLeft = timeout
    while 1:
        startedSelect = time.time()
        whatReady = select.select([mySocket], [], [], timeLeft)
        howLongInSelect = (time.time() - startedSelect)
        if whatReady[0] == []: # Timeout
            return "Request timed out."
        timeReceived = time.time()
        recPacket, addr = mySocket.recvfrom(1024)
        #Fill in start
        # the ICMP header that sits after the 20-byte IP header
        icmpHeader = recPacket[20:28]
        icmpType, code, checksum_val, packetID, sequence = struct.unpack("bbHHh", icmpHeader)

        # the error messages that replace a missing Echo Reply (BONUS 2)
        if icmpType == 3:  # Destination Unreachable
            errorCodes = {
                0: "Destination Network Unreachable",
                1: "Destination Host Unreachable",
                2: "Destination Protocol Unreachable",
                3: "Destination Port Unreachable",
            }
            return errorCodes.get(code, "Destination Unreachable (code %d)" % code)
        elif icmpType == 11:  # TTL expired
            return "TTL Expired in Transit"

        # the reply that matches our request by ID and sequence, giving the RTT
        if packetID == ID and sequence == seq:
            bytesInDouble = struct.calcsize("d")
            timeSent = struct.unpack("d", recPacket[28:28 + bytesInDouble])[0]
            return timeReceived - timeSent
        #Fill in end
        timeLeft = timeLeft - howLongInSelect
        if timeLeft <= 0:
            return "Request timed out."

def sendOnePing(mySocket, destAddr, ID, seq):
    # Header is type (8), code (8), checksum (16), id (16), sequence (16)
    myChecksum = 0
    # the dummy header with a 0 checksum
    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, seq)
    # the timestamp that becomes the payload
    data = struct.pack("d", time.time())
    # the checksum over header and data
    myChecksum = checksum(header + data)
    if sys.platform == 'darwin':
        myChecksum = htons(myChecksum) & 0xffff
    else:
        myChecksum = htons(myChecksum)
    # the real header with the correct checksum
    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, seq)
    packet = header + data
    mySocket.sendto(packet, (destAddr, 1))

def doOnePing(destAddr, timeout, ttl=None):
    icmp = getprotobyname("icmp")
    #Fill in start
    # the raw socket that speaks ICMP
    mySocket = socket(AF_INET, SOCK_RAW, icmp)
    #Fill in end
    # the low TTL that makes a router reply with a Time Exceeded error (BONUS 2)
    if ttl is not None:
        mySocket.setsockopt(IPPROTO_IP, IP_TTL, ttl)
    myID = os.getpid() & 0xFFFF  # the ID that tags our packets
    # the counters that survive across pings (seq + BONUS 1 stats)
    if not hasattr(doOnePing, 'seq'):
        doOnePing.seq = 0
        doOnePing.sent = 0
        doOnePing.rtts = []
    # the sequence number that increases for every packet
    doOnePing.seq = (doOnePing.seq + 1) & 0x7FFF
    seq = doOnePing.seq
    doOnePing.sent += 1
    #Fill in start
    # the request we send and the reply we wait for
    sendOnePing(mySocket, destAddr, myID, seq)
    delay = receiveOnePing(mySocket, myID, seq, timeout, destAddr)
    mySocket.close()
    if isinstance(delay, float):
        rttMs = delay * 1000
        doOnePing.rtts.append(rttMs)
        delay = "seq=%d RTT=%.3f ms" % (seq, rttMs)
    else:
        delay = "seq=%d %s" % (seq, delay)
    #Fill in end
    return delay

def ping(host, timeout=1, ttl=None):
    dest = gethostbyname(host)
    print("Pinging " + dest + " using Python:")
    print("")
    # the loop that pings once per second
    while 1 :
        delay = doOnePing(dest, timeout, ttl)
        print(delay)
        time.sleep(1)
    return delay

if __name__ == "__main__":
    # the menu that picks the host to ping
    presets = {
        "1": ("Localhost", "127.0.0.1"),
        "2": ("NASA (USA)", "www.nasa.gov"),
        "3": ("Yahoo (Singapore)", "sg.yahoo.com"),
        "4": ("ABC (Australia)", "www.abc.net.au"),
    }
    print("Select a host to ping:")
    for key in ("1", "2", "3", "4"):
        print("  %s. %s (%s)" % (key, presets[key][0], presets[key][1]))
    print("  5. Enter a host manually")
    print("  6. Demonstrate ICMP error (TTL Expired via TTL=1)")
    choice = input("Choice: ").strip()
    ttl = None
    if choice in presets:
        host = presets[choice][1]
    elif choice == "5":
        host = input("Enter host or IP: ").strip()
    elif choice == "6":
        host = input("Enter a distant host or IP [google.com]: ").strip() or "google.com"
        ttl = 1  # the TTL that expires at the first router and returns Type 11
    else:
        print("Invalid choice, defaulting to localhost.")
        host = "127.0.0.1"

    # the stats printed on Ctrl+C (BONUS 1); timeout=2 is the 2000 ms loss limit
    try:
        ping(host, timeout=2, ttl=ttl)
    except KeyboardInterrupt:
        print("\n--- Ping Statistics ---")
        sent = doOnePing.sent if hasattr(doOnePing, 'sent') else 0
        rtts = doOnePing.rtts if hasattr(doOnePing, 'rtts') else []
        received = len(rtts)
        loss = (sent - received) / sent * 100 if sent > 0 else 0
        print("%d packets sent, %d received, %.1f%% packet loss" % (sent, received, loss))
        if rtts:
            print("RTT min=%.3f ms / avg=%.3f ms / max=%.3f ms" % (
                min(rtts), sum(rtts) / len(rtts), max(rtts)))
