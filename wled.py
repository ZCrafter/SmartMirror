import socket

class WLED:
    def __init__(self,ip,port=21324):
        self.addr=(ip,port)
        self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    def send(self,pixels):
        data=bytearray()
        for r,g,b in pixels:
            data.extend((int(r),int(g),int(b)))
        self.sock.sendto(data,self.addr)
