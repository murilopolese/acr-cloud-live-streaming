#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014 Doreso
#

import sys
sys.path.append("./")
import subprocess
import os
import time
import datetime
import socket
import struct
from multiprocessing import Process
import hashlib
import logging
from functools import wraps
import errno
import os
import signal
import fcntl
import select
import acrcloudwrapper
import urllib
import urllib2
import base64
import hmac
import json

config = {}
codec = './ffmpeg'
logger = logging.getLogger('stream_client')

reload(sys)
sys.setdefaultencoding('utf-8')

def add_doc(fp, acrc_id, host=None, port=None):
    host = host or config['server_host']
    port = port or config['server_port']
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sign = acrc_id + (32-len(acrc_id))*chr(0)
    body = str(sign) + fp
    header = struct.pack('!cBBBIB', 'M', 1, 24, 1, len(body)+1, 1)
    sock.connect((host, port))
    sock.send(header+body)
    row = struct.unpack('!ii', sock.recv(8))
    #logger.info('add_doc %s %s %s' % (acrc_id, len(body), sock.recv(row[1])))

def __kill_all_process(proc):
    if not proc:
        return
    try:
        proc.kill()
        proc.terminate()
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait()
    except Exception, e:
        logger.error(e)

def ffmpeg_stream(stream):
    proc = subprocess.Popen([codec, '-loglevel', 'quiet', '-i', stream, '-ac', '1', '-ar', '8000', '-f', 'wav', 'pipe:1'],
                            stderr=subprocess.PIPE, stdout=subprocess.PIPE, preexec_fn=os.setsid)
    flags = fcntl.fcntl(proc.stdout, fcntl.F_GETFL)
    fcntl.fcntl(proc.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    return proc

def readstream(proc, size=1, timeout=5):
    stream = ''
    start = datetime.datetime.now()
    if size < 1 or not proc:
        return stream
    while len(stream) < size:
        try:
            ready,_,_ = select.select([proc.stdout],[],[], timeout)
            if not ready:
                return stream
            #buf = os.read(proc.stdout.fileno())
            buf = proc.stdout.read()
            stream = stream + buf
            now = datetime.datetime.now()
            if (now - start).seconds > timeout:
                return stream
        except Exception as e:
            if hasattr(e, 'errno') and e.errno == errno.EWOULDBLOCK:
                continue
            else:
                traceback.print_exc()
                return stream
    return stream


def stream_process(stream, acrc_id, host, port, duration=2, doc_time=6):
    proc = ffmpeg_stream(stream)
    last_buf = ''
    doc_pre_time = doc_time - duration

    while True:
        try:
            #now_buf = proc.stdout.read(duration*16000) # if 404 or cant connect, now_buf=None, return immediately
            now_buf = readstream(proc, duration*16000)
            if now_buf:
                cur_buf = last_buf + now_buf
                fp = acrcloudwrapper.gen_fp(cur_buf)
                if fp:
                    #logger.info("curbuflen="+str(len(cur_buf)) + ", fplen=" + str(len(fp)))
                    try:
                        add_doc(fp, acrc_id, host, port)
                    except Exception, e:
                        last_buf = cur_buf
                        if len(last_buf) > 10*16000:
                            last_buf = last_buf[len(last_buf)-10*16000:]
                        logger.warning(stream+' add_doc failed ' + str(e))
                        continue
                last_buf = cur_buf
                if len(last_buf) > doc_pre_time*16000:
                    last_buf = last_buf[-1*doc_pre_time*16000:]
            else:
                time.sleep(1)
                raise Exception('404 or something')
        except KeyboardInterrupt:
            #if proc:
            #    os.killpg(proc.pid, signal.SIGTERM)
            #    proc = None
            __kill_all_process(proc)
            proc = None
            return
        except Exception, e:
            logger.warning('%s:%s %s' % (stream, acrc_id, str(e)))
            #if proc:
            #    os.killpg(proc.pid, signal.SIGTERM)
            #    proc = None
            __kill_all_process(proc)
            proc = ffmpeg_stream(stream)
            last_buf = ''

def get_remote_config():
    try:
        timestamp = time.time()
        signature = base64.b64encode(hmac.new(config['access_secret'], config['access_key']+str(timestamp), digestmod=hashlib.sha1).hexdigest())
        values = {'access_key' : config['access_key'], 'timestamp': timestamp,
            'sign' : signature}
        data = urllib.urlencode(values)
        url = 'http://console.acrcloud.com/service/channels?'+data
        req = urllib2.Request(url)
        response = urllib2.urlopen(req)
        recv_msg = response.read()
        json_res = json.loads(recv_msg)
        if json_res['response']['status']['code'] == 0:
            config['streams'] = json_res['response']['metainfos']
        else:
            print('%s' % json_res)
    except Exception, e:
        print('get_remote_config : %s' % str(e))
        sys.exit(0)

def parse_config():
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        confpath = sys.argv[1]
    else:
        confpath = './client.conf'
    try:
        initconfig = {}
        execfile(confpath, initconfig)
        if initconfig.get('debug'):
            DEBUG = True
        else:
            DEBUG = False
        config['access_key'] = os.getenv('ACCESS_KEY', initconfig['access_key'])
        config['access_secret'] = os.getenv('ACCESS_SECRET', initconfig['access_secret'])
        config['remote'] = initconfig.get('remote')
        if initconfig.get('remote'):
            get_remote_config()
        else:
            config['streams'] = initconfig['source']
            config['server_host'] = initconfig['server']['host']
            config['server_port'] = initconfig['server']['port']

    except Exception, e:
        print e
        print "Error: Load ./client.conf failed.\nPlease make sure ./client.conf exist and no syntax error\n"
        sys.exit(1)

    FORMAT = '%(asctime)-15s %(message)s'
    logging.basicConfig(format=FORMAT)
    logger = logging.getLogger('stream_client')
    if DEBUG:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.ERROR)


def main():
    parse_config()
    if config['remote']:
        for stream in config['streams']:
            Process(target=stream_process, args=(stream['url'], stream['acrc_id'], stream['host'], stream['port'])).start()
    else:
        for stream in config['streams']:
            Process(target=stream_process, args=(stream[0], stream[1], config['server_host'], config['server_host'])).start()


if __name__ == '__main__':
    main()
