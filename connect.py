"""
This is the core connection manager.
"""

from socket import socket, AF_INET, SOCK_STREAM
try:
    import thread
except ImportError:
    import _thread as thread


def colorize(text, color):
    """
    Adds color (code @color) to text @text, which can then be embedded in a 
    message.
    """
    # \x03<zero-padded-to-width-2-color><text>\x03
    return '\x03%02d%s\x03' % (color, text)


def bold(text):
    """
    Returns text @text with bold formatting, which can then be embedded in a 
    message.
    """
    # \x02<text>\x02
    return '\x02%s\x02' % text


def underline(text):
    """
    Returns text @text with underline formatting, which can then be embedded in 
    a message.
    """
    # \x1f<text>\x1f
    return '\x1f%s\x1f' % text


class IRCConn(object):
    
    """
    This class handles the connection with the IRC server.
    It connects and sends and receives messages.
    """
    
    #### Initializers ########
    
    def __init__(self, handler):
        self.handler = handler
        i = handler.ident
        self.ident = i.ident
        self.serv = i.serv
        self.host = i.host
        self.name = i.name
        self.nick = i.nick
        self.join_first = i.joins
        self.port = getattr(i, 'port', 6667)
        self.channels = set()
    
    def connect(self):
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self._send('USER %s %s %s :%s' % 
                   (self.ident, self.host, self.serv, self.name))
        self._send('NICK %s' % self.nick)
        # wait until we have received the MOTD in full before proceeding
    
    def mainloop(self):
        """
        The mainloop.
        """
        # Rather than `while True:` for speed
        while 1:
            line = self.receive()
            # Yeah, threading. TODO: Allow disabling?
            thread.start_new_thread(self.parse, (line,))
    
    #### Commands ############
    
    def say(self, msg, chan, to=None):
        """
        Say @msg on @chan.
        """
        if to is None:
            prefix = ''
        else:
            to = '%s: ' % to
        
        for line in msg.splitlines():
            self._send('PRIVMSG %s :%s%s' % (chan, prefix, line))
    
    def whois(self, nick):
        """
        Send a WHOIS command for nick @nick.
        """
        self._send('WHOIS %s' % nick)
    
    def who(self, chan_nick):
        """
        Send a WHO command for nick or channel @chan_nick.
        """
        self._send('WHO %s' % chan_nick)
    
    def names(self, chan):
        """
        Send a NAMES command for channel @chan.
        """
        self._send('NAMES %s' % chan)
    
    def ident(self, pswd):
        """
        Do a NickServ identify with @pswd.
        """
        self.say('identify %s' % pswd, 'NickServ')
    
    def describe(self, msg, chan):
        """
        Describe the user as doing @msg on channel @chan.
        """
        self.say('\x01ACTION %s\x01' % msg, chan)
    
    
    def mode(self, mode, mask, chan):
        """
        Set mode @mode for mask @mask on channel @channel.
        """
        self._send('MODE %s %s %s' % (chan, mode, mask))
    
    # A few common mode shortcuts
    def ban(self, mask, chan):
        """
        Ban mask @mask from channel @chan.
        """
        self.mode('+b', mask, chan)
    
    def unban(self, mask, chan):
        """
        Unban mask @mask from channel @chan.
        """
        self.mode('-b', mask, chan)
    
    def voice(self, mask, chan):
        """
        Give mask @mask voice on channel @chan.
        """
        self.mode('+v', mask, chan)
    
    def devoice(self, mask, chan):
        """
        Take voice from mask @mask on channel @chan.
        """
        self.mode('-v', mask, chan)
    
    def op(self, mask, chan):
        """
        Give mask @mask OP status on channel @chan.
        """
        self.mode('+o', mask, chan)
    
    def deop(self, mask, chan):
        """
        Take OP status from mask @mask on channel @chan.
        """
        self.mode('-o', mask, chan)
    
    
    def kick(self, chan, nicks=[], reason=None):
        """
        Kick nicks @nicks from channel @chan for reason @reason.
        """
        if not nicks:
            return
        
        if reason is None:
            r = ''
        else:
            r = ' :%s' % reason
        
        self._send('KICK %s %s%s' % (chan, ','.join(nicks), r))
    
    def join(self, chan):
        """
        Join channel @chan.
        """
        self._send('JOIN %s' % chan)
        self.channels.add(chan)
        self.handler.handle_join(chan)
    
    def leave(self, msg, chan):
        """
        Leave channel @chan with reason @msg.
        """
        self._send('PART %s :%s' % (chan, msg))
        if chan in self.channels:
            self.channels.remove(chan)
    
    #### Internals ###########
    
    def _send(self, msg):
        """
        Send something (anything) to the IRC server.
        """
        print('Sending: %s\r\n' % msg)
        self.sock.send(('%s\r\n' % msg).encode())
    
    def pong(self, trail):
        self._send('PONG %s' % trail)
    
    def receive(self):
        """
        Read from the socket until we reach the end of an IRC message.
        Attempt to decode the message and return it.
        Call handle_encoding_error() if unsuccessful.
        """
        buf = []
        while True:
            nxt_ch = None
            ch = self.sock.recv(1)
            if ch == b'\r':
                nxt_ch = self.sock.recv(1)
                if nxt_ch == b'\n':
                    try:
                        line = b''.join(buf).decode()
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        self.handle_encoding_error()
                        return ''
                    print('received: %s' % line)
                    return line
            buf.append(ch)
            if nxt_ch:
                buf.append(nxt_ch)
            
        if not line.strip():
            return None
        else:
            try:
                parsable = line.strip(b'\r\n').decode()
                print('Received: %s' % parsable)
                return parsable
            except (UnicodeEncodeError, UnicodeDecodeError):
                self.handle_encoding_error()
    
    def parse(self, line):
        if not line:
            # empty line; this should throw up an error.
            return
        line = line.strip('\r\n')
        tokens = line.split(' ')
        if tokens[0].startswith(':'):
            prefix = tokens.pop(0)[1:].strip(':')
        else:
            prefix = ''
        
        # Apparently, mIRC does not send uppercase commands (from Twisted's IRC)
        cmd = tokens.pop(0).upper()
        if cmd == '433':       # nick already in use
            self.nick += '_'
            self._send('NICK %s' % self.nick)
        elif cmd == '376':     # end of MOTD
            self.on_connect()
        elif cmd == '422':     # No MOTD file
            self.on_connect()
        elif cmd == '353':      # Names list
            self.handler.handle_name_list(tokens)
        elif cmd == 'PING':
            self.pong(' '.join(tokens))
        elif cmd == 'ERROR':
            self.handle_error(tokens)
        elif cmd == 'KICK':
            self.handler.handle_kick(tokens, prefix)
        elif cmd == 'JOIN':
            if prefix.split('!')[0] != self.nick:
                self.handler.handle_other_join(tokens, prefix)
        elif cmd == 'PRIVMSG':
            self.handler.handle_privmsg(tokens, prefix)

    def handle_encoding_error(self):
        print('Encoding error encountered.')
    
    def handle_error(self, tokens):
        print('Error. tokens: %s' % tokens)
        self.connect()
    
    def on_connect(self):
        """
        Called once we have connected to and identified with the server.
        Mainly joins the channels that we want to join at the start.
        """
        for chan in self.join_first:
            self.join(chan)
