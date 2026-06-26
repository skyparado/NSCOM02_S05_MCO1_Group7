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
        thisVal = ord(string[count+1]) * 256 + ord(string[count])
        csum = csum + thisVal
        csum = csum & 0xffffffff
        count = count + 2
    if countTo < len(string):
        csum = csum + ord(string[len(string) - 1])
        csum = csum & 0xffffffff
    csum = (csum >> 16) + (csum & 0xffff)
    csum = csum + (csum >> 16)
    answer = ~csum
    answer = answer & 0xffff
    answer = answer >> 8 | (answer << 8 & 0xff00)
    return answer

# Makes it a string so its a valid check sum, this entire thing is added/double check if this allowed...
import ast
def checksum(string):
    if isinstance(string, str):
        if string.startswith("b'") or string.startswith('b"'):
            string = ast.literal_eval(string)
        else:
            string = string.encode('latin-1')
    csum = 0
    countTo = (len(string) // 2) * 2
    count = 0
    while count < countTo:
        thisVal = string[count + 1] * 256 + string[count]
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

def receiveOnePing(mySocket, ID, timeout, destAddr):
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
        #Fetch the ICMP header from the IP packet
        icmpHeader = recPacket[20:28]
        icmpType, code, checksum_val, packetID, sequence = struct.unpack("bbHHh", icmpHeader)

        # BONUS 2: Parse and display ICMP error codes when Echo Reply is not received
        if icmpType == 3:  # Destination Unreachable
            errorCodes = {
                0: "Destination Network Unreachable",
                1: "Destination Host Unreachable",
                2: "Destination Protocol Unreachable",
                3: "Destination Port Unreachable",
            }
            return errorCodes.get(code, "Destination Unreachable (code %d)" % code)
        elif icmpType == 11:  # Time Exceeded (TTL Expired)
            return "TTL Expired in Transit"

        if packetID == ID:
            bytesInDouble = struct.calcsize("d")
            timeSent = struct.unpack("d", recPacket[28:28 + bytesInDouble])[0]
            return timeReceived - timeSent
        #Fill in end
        timeLeft = timeLeft - howLongInSelect
        if timeLeft <= 0:
            return "Request timed out."

def sendOnePing(mySocket, destAddr, ID):
    # Header is type (8), code (8), checksum (16), id (16), sequence (16)
    myChecksum = 0
    # Make a dummy header with a 0 checksum
    # struct -- Interpret strings as packed binary data
    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)
    data = struct.pack("d", time.time())
    # Calculate the checksum on the data and the dummy header.
    myChecksum = checksum(str(header + data))
    # Get the right checksum, and put in the header
    if sys.platform == 'darwin':
        # Convert 16-bit integers from host to network byte order
        myChecksum = htons(myChecksum) & 0xffff
    else:
        myChecksum = htons(myChecksum)
    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)
    packet = header + data
    mySocket.sendto(packet, (destAddr, 1)) # AF_INET address must be tuple, not str
    # Both LISTS and TUPLES consist of a number of objects
    # which can be referenced by their position number within the object.

def doOnePing(destAddr, timeout):
    icmp = getprotobyname("icmp")
    # SOCK_RAW is a powerful socket type. For more details: http://sockraw.org/papers/sock_raw
    #Fill in start
    #create socket
    mySocket = socket(AF_INET, SOCK_RAW, icmp)
    #Fill in end
    myID = os.getpid() & 0xFFFF # Return the current process i
    #Fill in start
    #send a single ping using the socket, dst addr and ID
    sendOnePing(mySocket, destAddr, myID)
    #add delay using timeout
    delay = receiveOnePing(mySocket, myID, timeout, destAddr)
    #close socket
    mySocket.close()
    # Track sequence number for per-packet output (spec: print seq + RTT in ms)
    # Also accumulate stats for BONUS 1
    if not hasattr(doOnePing, 'seq'):
        doOnePing.seq = 0
        doOnePing.sent = 0
        doOnePing.rtts = []
    doOnePing.seq = (doOnePing.seq + 1) & 0xFFFF
    doOnePing.sent += 1
    if isinstance(delay, float):
        rttMs = delay * 1000
        doOnePing.rtts.append(rttMs)
        delay = "seq=%d RTT=%.3f ms" % (doOnePing.seq, rttMs)
    else:
        delay = "seq=%d %s" % (doOnePing.seq, delay)
    #Fill in end
    return delay

def ping(host, timeout=1):
    # timeout=1 means: If one second goes by without a reply from the server,
    # the client assumes that either the client's ping or the server's pong is lost
    dest = gethostbyname(host)
    print("Pinging " + dest + " using Python:")
    print("")
    # Send ping requests to a server separated by approximately one second
    while 1 :
        delay = doOnePing(dest, timeout)
        print(delay)
        time.sleep(1)# one second
    return delay

# BONUS 1: RTT Summary Stats — wrap call to catch Ctrl+C and print min/max/avg + packet loss
# timeout=2 to match spec requirement of 2000 ms before assuming packet is lost
if __name__ == "__main__":
    try:
        ping("127.0.0.1", timeout=2)
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
