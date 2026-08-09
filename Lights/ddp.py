import socket

class DDP:
    def __init__(self,ip,port=4048):
        self.addr=(ip,port)
        self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)

    def send(self,pixels):
        data=bytearray()
        for r,g,b in pixels:
            data.extend([int(r),int(g),int(b)])
        header=bytes([0x41,0,0,0,0,0,0,0,0,0])
        self.sock.sendto(header+data,self.addr)
