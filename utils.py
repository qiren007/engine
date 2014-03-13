'''
Created on 7 Mar, 2014

@author: qiren
'''
from http.client import HTTPConnection
from django.utils import simplejson
import subprocess
import log as logging
import os
import settings
import time
import threading

logger = logging.getLogger('engine')

OS_FAMILY = ['windows 7', 'ubuntu']


class ExecProcError(IOError):
    MSG_TMPL = ('Description: %(description)s\n'
                'Command: %(cmd)s\n'
                'Exit code: %(exit_code)s\n'
                'Reason: %(reason)s\n'
                'Stdout: %(stdout)r\n'
                'Stderr: %(stderr)r')

    def __init__(self, stdout=None, stderr=None,
                exit_code=None, cmd=None, reason=None, description=None):
        if not description:
            self.description = ''
        else:
            self.description = description

        if not cmd:
            self.cmd = '-'
        elif isinstance(cmd, list):
            self.cmd = ' '.join(cmd)
        else:
            self.cmd = cmd

        if not isinstance(exit_code, int):
            self.exit_code = '-'
        else:
            self.exit_code = exit_code

        if not stderr:
            self.stderr = ''
        else:
            self.stderr = stderr

        if not stdout:
            self.stdout = ''
        else:
            self.stdout = stdout

        if reason:
            self.reason = reason
        else:
            self.reason = 'unknow error'

        msg = self.MSG_TMPL % {
            'description': self.description,
            'cmd': self.cmd,
            'exit_code': self.exit_code,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'reason': self.reason,
        }
        IOError.__init__(self, msg)


def release_port(port):
    cmd = 'lsof -i :' + str(port)
    try:
        output = exec_process(cmd, shell=True)
    except ExecProcError as ex:
        logger.error(ex)
    else:
        out = output[0].split('\n')
        find_pid_idx = out[0].split(' ')
        idx = 0
        for i in find_pid_idx:
            if i != '' and i.upper() != 'PID':
                idx += 1
            if i.upper() == 'PID':
                break
        if len(out) > 1:
            all_proc = out[1:]
            for i in all_proc:
                if len(i) == 0:
                    break
                proc_list = i.split(' ')
                plist = []
                for j in proc_list:
                    if j != '':
                        plist.append(j)
                pid = plist[idx]
                release_cmd = 'kill -9 ' + pid
                try:
                    output = exec_process(release_cmd)
                except ExecProcError as ex:
                    logger.error('fail to release port %d, reason: %s' % (port, ex))
                else:
                    logger.info('release port %d successfully' % port)


def timeout(p, port):
    start = time.time()
    while not p.poll():
        time.sleep(2)
        end = time.time()
        if end - start > settings.TIMEOUT:
            release_port(port)
            break


def exec_process(args, encoding='utf-8', input_data=None, rc_list=None, env=None, shell=True, need_timeout=False):
    """
    use for executing commande

    @param args: the command that need execute
    @param encoding: system stdout encoding
    @param input_data: input data that send to the stdin of process, default is None
    @param rc_list: valid return value list, default is None
    @param shell: decide if we should use unix shell function like os.system()
    @return:  tuple of stdout and stderr
    """
    if rc_list is None:
        rc_list = [0]
    if need_timeout:
        rc_list = [0, 1, 137]

    try:
        p = subprocess.Popen(args,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             env=env,
                             shell=shell)
        if not p.poll() and need_timeout:
            port_str = args.split(' ')[-1]
            port = int(port_str.strip(':')) + 5900
            thr = threading.Thread(target=timeout, args=(p, port))
            thr.daemon = True
            thr.start()
        out, err = p.communicate(input_data)
    except OSError as ex:
        raise ExecProcError(stderr=ex,
                            exit_code=-1,
                            cmd=args,
                            reason=' OS Error',
                            )
    else:
        if p.returncode not in rc_list:
            cmd = None
            if isinstance(args, str):
                cmd = args
            elif isinstance(args, list):
                cmd = ' '.join(args)
            #logger.debug('stdout: ' + out.decode(sys.stdin.encoding))
            #logger.debug('stderr: ' + err.decode(sys.stdin.encoding))
            raise ExecProcError(stdout=out.decode(encoding),
                                stderr=err.decode(encoding),
                                exit_code=p.returncode,
                                cmd=cmd,
                                reason=err.decode(encoding),
                                )
    return (out.decode(encoding), err.decode(encoding))


class KvmTool:

    @classmethod
    def launch(self, image_type, image_name):
        image_type = image_type.lower()
        if image_type in OS_FAMILY:
            if image_type == 'windows 7':
                for i in range(30):
                    cmd = 'kvm -m 2048 -drive file=' + image_name + \
                    ',if=virtio,boot=on -net nic,model=virtio -net user -boot c -nographic -vnc :'
                    cmd += str(i)
                    logger.info(cmd)
                    try:
                        output = exec_process(cmd, need_timeout=True)
                    except ExecProcError as ex:
                        logger.warning(ex)
                    else:
                        logger.info(output[0])
                        logger.info('dispatch port: %d' % (i + 5900))
                        return (True, i + 5900)
            elif image_type == 'ubuntu':
                for i in range(30):
                    cmd = 'kvm -m 2048 -drive file=' + image_name + \
                    ',boot=on -net nic -net user -boot c -nographic -vnc :'
                    cmd += str(i)
                    try:
                        output = exec_process(cmd, need_timeout=True)
                    except ExecProcError as ex:
                        logger.warning(ex)
                    else:
                        logger.info(output[0])
                        logger.info('dispatch port: %d' % (i + 5900))
                        return (True, i + 5900)
        else:
            logger.error('unknow image type')
            return (False, None)


class GlanceService:
    def __init__(self, path, image_name, is_public=True, container_format='ovf', disk_format='qcow2'):
        """
        @param path: the path of image
        @param name: the name of image you want to see on openstack
        """
        self.path = path
        self.image_name = image_name
        self.is_public = is_public
        self.container_format = container_format
        self.disk_format = disk_format
        self.set_env()

    def get_tenant_id_and_token_id(self):
        body = {
                "auth": {
                         "passwordCredentials": {
                                "username": settings.OS_USERNAME,
                                "password": settings.OS_PASSWORD,
                        },
                         "tenantName": settings.OS_TENANT_NAME,
                },
        }
        method = "POST"
        headers = {'Content-type': 'application/json','Accept': 'application/json'}
        try:
            conn = HTTPConnection(settings.OS_URL, settings.OS_AUTH_PORT)
            conn.request(method, '/v2.0/tokens/', simplejson.dumps(body, 'utf-8'), headers)
            resp = conn.getresponse()
        except Exception:
            pass
        else:
            data = resp.read().decode('utf-8')
            rs = simplejson.loads(data)
        return (rs['access']['token']['tenant']['id'], rs['access']['token']['id'])

    def set_env(self):
        env = os.environ.copy()
        env['PATH'] = '/usr/bin;' + env['PATH']
        tenant_id, token = self.get_tenant_id_and_token_id()
        env['OS_USERNAME'] = settings.OS_USERNAME
        env['OS_PASSWORD'] = settings.OS_PASSWORD
        env['OS_TENANT_ID'] = tenant_id
        env['OS_AUTH_URL'] = settings.OS_AUTH_URL
        env['OS_IMAGE_URL'] = settings.OS_IMAGE_URL
        env['OS_AUTH_TOKEN'] = token
        return env

    def create(self):
        cmd = 'glance image-create --name=\"' + self.image_name + '\"' + ' --is-public=' + \
                str(self.is_public) + ' --container-format=' + self.container_format + ' --disk-format=' + \
                self.disk_format + ' --min-ram=2048 --min-disk=20 < ' + self.path
#         cmd = 'glance add name=\"' + self.name + '\"' + " is-public=" + str(self.is_public) + ' container_format=' + \
#             self.container_format + ' disk_format=' + self.disk_format + ' < ' + self.image_name
        try:
            output = exec_process(cmd, env=self.set_env())
        except ExecProcError as ex:
            logger.error(ex)
            return False
        else:
            logger.info(output[0])
        return True

if __name__ == '__main__':
    pass
    import os
    import settings
    KvmTool.launch('ubuntu', os.path.join(settings.TEMP, 'cirros.img'))
    gt = GlanceService(os.path.join(settings.TEMP, 'cirros.img'), 'test_qqqq', True)
    gt.create()
#     cmd = 'glance add name=\"win7.img\" + is-public=True container_format=qcow2 disk_format=ovf < /home/os/workspace/engine/local_image_warehouse/win7.img'
#     os.system(cmd)