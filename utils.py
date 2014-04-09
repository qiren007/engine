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
import shutil
import yaml
import signal

logger = logging.getLogger('engine')


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
        output = exec_process(cmd, rc_list=[0, 1], shell=True)
    except ExecProcError as ex:
        logger.error(ex)
        return False
    else:
        if output[0] == '':
            logger.info('port %d is actually not used, abort to release it' % port)
            return True
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
                        return True
                    return False
            return True


def exec_process(args, encoding='utf-8', input_data=None, rc_list=None, env=None, shell=True, timeout=None):
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
    out, err = b'', b''
    try:
        p = subprocess.Popen(args,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             env=env,
                             shell=shell,
                             preexec_fn=os.setsid)
        out, err = p.communicate(input_data, timeout=timeout)
    except OSError as ex:
        raise ExecProcError(stderr=ex,
                            exit_code=-1,
                            cmd=args,
                            reason=' OS Error',
                            )
    except subprocess.TimeoutExpired as ex:
        os.killpg(p.pid, signal.SIGTERM)
        raise ExecProcError(stderr=ex,
                            exit_code=-2,
                            cmd=args,
                            reason='timeout for execution')
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
    def __init__(self):
        self.unrelease_resouce = None

    def _action(self, cmd):
        for i in map(lambda x: (cmd + str(x), x + 5900), range(100)):
            command, port = i
            logger.info(command)
            try:
                self.unrelease_resouce = port
                exec_process(command, timeout=settings.TIMEOUT)
            except ExecProcError as ex:
                if ex.exit_code == -2:
                    logger.error(ex)
                    if release_port(port):
                        self.unrelease_resouce = None
                elif ex.exit_code == 1:
                    logger.info('port is busy, change to another one')
                else:
                    logger.warning(ex)
            else:
                logger.info('dispatch port: %d' % port)
                return (True, port)

    def launch(self, image_type, image_name):
        image_type = image_type.lower()
        if image_type in settings.OS_FAMILY['nt']:
            cmd = 'kvm -m 2048 -drive file=' + image_name + \
            ',if=virtio,boot=on -net nic,model=virtio -net user -boot c -nographic -vnc :'
            return self._action(cmd)
        elif image_type in settings.OS_FAMILY['posix']:
            cmd = 'kvm -m 2048 -drive file=' + image_name + \
            ',boot=on -net nic -net user -boot c -nographic -vnc :'
            return self._action(cmd)
        logger.error('launch vm error, unknow image type')
        return (False, None)

    def resource_grabber(self):
        if self.unrelease_resouce:
            logger.info('start grabbing resource of kvm tools...\nused port: %d' % self.unrelease_resouce)
            if release_port(self.unrelease_resouce):
                self.unrelease_resouce = None
                logger.info('grab port successfully')
            else:
                logger.warning('can not grab resource, port %d occupied' % self.unrelease_resouce)
        else:
            logger.info('no resource to grab, abort it')


class GlanceService:
    def __init__(self):
        """
        @param path: the path of image
        @param name: the name of image you want to see on openstack
        """
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

    def _action(self, cmd):
        try:
            output = exec_process(cmd, env=self.set_env())
        except ExecProcError as ex:
            logger.error(ex)
            return False
        else:
            logger.info(output[0])
        return True

    def create(self, path, image_name, is_public=True, container_format='ovf', disk_format='qcow2'):
        cmd = 'glance image-create --name=\"' + image_name + '\"' + ' --is-public=' + \
                str(is_public) + ' --container-format=' + container_format + ' --disk-format=' + \
                disk_format + ' --min-ram=2048 --min-disk=20 < ' + path
#         cmd = 'glance add name=\"' + self.name + '\"' + " is-public=" + str(self.is_public) + ' container_format=' + \
#             self.container_format + ' disk_format=' + self.disk_format + ' < ' + self.image_name
        return self._action(cmd)

    def download(self, image, save_as=None):
        cmd = 'glance image-download %s %s' % (('--file %s' % save_as) if save_as else '', image)
        return self._action(cmd)

class ImgHandler:
    TMP_PATH = '/tmp/'
    def __init__(self, img_path, fs_type, img_id, img_os_type):
        self.img_path = img_path
        self.fs_type = fs_type
        self.img_id = img_id
        if img_os_type == 'nt':
            self.agent_defaut_dir = r'Program Files/%s' % settings.AGENT_DIR_NAME
        else:
            self.agent_defaut_dir = r'usr/local/%s' % settings.AGENT_DIR_NAME
        self.unrelease_resources = {'files_dirs': set(),
                                    'mount_points': set(),
                                    'loop_device': set()}
        

    def _find_loop_dev(self):
        cmd = 'losetup -f'
        try:
            output = exec_process(cmd)
        except ExecProcError as ex:
            logger.error('fail to find available loop device, reason: %s' % ex)
            return None
        else:
            logger.info('find the available loop device %s' % output[0])
            return output[0].strip('\n')

    def _ensure_dir(self, expect_dir):
        idx = 0
        origin_dir = expect_dir
        while os.path.isdir(expect_dir):
            expect_dir = origin_dir
            expect_dir += str(idx)
            idx += 1
        try:
            os.mkdir(expect_dir)
        except Exception:
            return None
        else:
            return expect_dir

    def _clean_tmp_dir(self, tmp_dir):
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            return False
        return True

    def _mount_fs(self):
        loop_dev = self._find_loop_dev()
        res = ()
        if loop_dev:
            res = (loop_dev, [])
            setup_device = ['losetup', loop_dev, self.img_path]
            map_device = ['kpartx', '-av', loop_dev]
            try:
                exec_process(setup_device, shell=False)
                exec_process(map_device, shell=False)
            except ExecProcError as ex:
                logger.error(ex)
                if ex.cmd == ' '.join(map_device):
                    logger.error('fail to release loop device %s, add to unrelease resource' % loop_dev)
                    self.unrelease_resources['loop_device'].add(loop_dev)
                return (False, res)
            else:
                count = 1
                mount_dir = os.path.join(self.TMP_PATH, self.img_id)
                mount_dir = self._ensure_dir(mount_dir)
                self.unrelease_resources['files_dirs'].add(mount_dir)
                self.unrelease_resources['loop_device'].add(loop_dev)
                if mount_dir:
                    while os.path.exists('/dev/mapper/%sp%d' % (os.path.basename(loop_dev), count)):
                        m_dir = self._ensure_dir(os.path.join(mount_dir, str(count)))
                        if m_dir:
                            mount_device = 'mount -t %s /dev/mapper/%sp%d %s' % (self.fs_type, os.path.basename(loop_dev), count, m_dir)
                            try:
                                exec_process(mount_device)
                            except ExecProcError as ex:
                                logger.error(ex)
#                                 return (False, res)
                            else:
                                self.unrelease_resources['mount_points'].add(m_dir)
                                res[1].append(m_dir)
                                logger.info('mount %sp%d successfully' % (os.path.basename(loop_dev), count))
                        count += 1
                    return (True, res)
        return (False, res)

    def _force_umount_dir(self, mount_point):
        cmd_list = ['fuser -k %s', 'umount %s']
        cmd_list = list(map(lambda x: x % mount_point, cmd_list))
        try:
            for cmd in cmd_list:
                exec_process(cmd)
        except ExecProcError as ex:
            logger.error(ex)
            return False
        return True

    def _del_loop_device(self, loop_dev):
        unmap_device = 'kpartx -dv %s' % loop_dev
        shutdown_device = 'losetup -d %s' % loop_dev
        try:
            exec_process(unmap_device)
            exec_process(shutdown_device)
        except ExecProcError as ex:
            logger.error(ex)
            return False
        else:
            self.unrelease_resources['loop_device'].discard(loop_dev)
            return True

    def _umount_fs(self, loop_dev, dir_list):
        par_dir = None
        for d in  dir_list:
            if not par_dir:
                par_dir = os.path.dirname(d)
            umount = 'umount %s' % d
            try:
                exec_process(umount)
            except ExecProcError as ex:
                logger.error(ex)
                if self._force_umount_dir(d):
                    self.unrelease_resources['mount_points'].discard(d)
                    self._clean_tmp_dir(d)
            else:
                self.unrelease_resources['mount_points'].discard(d)
                self._clean_tmp_dir(d)
        if len(os.listdir(par_dir)) == 0:
            self.unrelease_resources['files_dirs']
            self._clean_tmp_dir(par_dir)
        if self._del_loop_device(loop_dev):
            logger.info('umount fs successfully')

    def _find_agent_dir(self, path):
        test_dir = os.path.join(path, self.agent_defaut_dir)
        res_list = []
        if os.path.isdir(test_dir):
            res_list.append(test_dir)
        else:
            find_dir = 'find %s -name %s -type d' % (path, settings.AGENT_DIR_NAME)
            try:
                output= exec_process(find_dir)
            except ExecProcError as ex:
                logger.error(ex)
            else:
                for i in output[0].split('\n'):
                    res_list.append(i)
        return list(filter(lambda x: x != '', res_list))

    def inject_template_id_to_vm(self, template_id):
        res = self._mount_fs()
        ret = False
        if res[0]:
            for path in res[1][1]:
                agent_dir = self._find_agent_dir(path)
                for i in agent_dir:
                    new_agent_settings = []
                    agent_settings_path = os.path.join(i, settings.AGENT_SETTINGS)
                    with open(agent_settings_path, 'r') as f:
                        agent_settings = f.readlines()
                    for i in agent_settings:
                        new_agent_settings.append('%s = %s\n' % (settings.AGENT_VM_ID_KEY, template_id) if settings.AGENT_VM_ID_KEY in i else i)
                    with open(agent_settings_path, 'w') as f:
                        f.writelines(new_agent_settings)
            ret = True
            logger.info('inject template id to vm successfully, start to umount fs...')
        self._umount_fs(res[1][0], res[1][1])
        return ret

    def inject_data_to_vm(self, data):
        ret = False
        res = self._mount_fs()
        if res[0]:
            for path in res[1][1]:
                agent_dir = self._find_agent_dir(path)
                for i in agent_dir:
                    db_path = os.path.join(i, settings.AGENT_DB_NAME)
                    if os.path.isdir(db_path):
                        try:
                            f = open(os.path.join(db_path, settings.AGENT_INFO_FROM_ENGINE_FILENAME), 'w')
                            yaml.dump(data, f, default_flow_style=False)
                        except Exception as ex:
                            logger.error(ex)
                        else:
                            logger.info('inject data successfully')
                            ret = True
                            f.close()
        if not ret:
            logger.error('fail to inject data to vm')
        logger.info('start to unmount fs...')
        self._umount_fs(res[1][0], res[1][1])
        return ret


    def get_unrelease_resouces(self):
        for i in self.unrelease_resources:
            if not self.unrelease_resources[i]:
                return self.unrelease_resources
        return None

    def format_unrelease_resouces(self):
        return 'used files or dirs:%s\nmount points:%s\nused loop device:%s\n' % \
                (','.join(self.unrelease_resources['files_dirs']),
                 ','.join(self.unrelease_resources['mount_points']),
                 ','.join(self.unrelease_resources['loop_device']))

    def resource_grabber(self):
        import copy
        if not self.get_unrelease_resouces():
            logger.info('no resource to grab')
        else:
            logger.info('start grabbing resources...\n%s' % self.format_unrelease_resouces())
            tmp_resources = copy.deepcopy(self.unrelease_resources)
            for i in tmp_resources:
                for j in tmp_resources[i]:
                    if (i == 'mount_points' and self._force_umount_dir(j)) or \
                       (i == 'loop_dev' and self._del_loop_device(j)) or \
                       (i == 'files_dirs' and self._clean_tmp_dir(j)):
                        self.unrelease_resources[i].discard(j)
            del tmp_resources
            logger.info('after grabbing...\n%s' % self.format_unrelease_resouces())

def download(url, save_dir, name):
    cmd = ['wget', '-c', '-a', settings.DOWNLOAD_FILE_NAME, '-O', os.path.join(save_dir, name), url]
    try:
        exec_process(cmd, shell=False)
    except ExecProcError as ex:
        logger.error(ex)
        return False
    return True


def clean_tmp_file(path):
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass


def check_integrity(file, checksum):
    from hashlib import md5
    stat_info = os.stat(file)
    m = md5()
    f = open(file, 'rb')
    def big_file_md5():
        buffer = 8192
        while True:
            chunk = f.read(buffer)
            if not chunk: break
            m.update(chunk)
        return m.hexdigest()
    if int(stat_info.st_size) / (1024 * 1024) >= 1000:
        return checksum == big_file_md5()
    m.update(f.read())
    f.close()
    return checksum == m.hexdigest()

if __name__ == '__main__':
#     KvmTool.launch('ubuntu', os.path.join(settings.TEMP, 'cirros.img'))
#     gt = GlanceService(os.path.join(settings.TEMP, 'cirros.img'), 'test_qqqq', True)
#     gt.create()
#     cmd = 'glance add name=\"win7.img\" + is-public=True container_format=qcow2 disk_format=ovf < /home/os/workspace/engine/local_image_warehouse/win7.img'
#     os.system(cmd)
#     test = ImgHandler('/home/os/Templates/workspace/engine/local_image_warehouse/0_test', 'ntfs', 'win7_test_injection', 'nt')
#     test.inject_data_to_vm({'test2': {'test2': {'a': 'a', 'b': 'b'}}})
#     test.inject_template_id_to_vm('test_id')
#     download('http://192.168.0.134:8000/template/downloadTemplate/?id=2', '/home/os/Downloads', 'test.img')
#     print('finish')
#     release_port(5900)
    print(check_integrity('local_image_repository/72ab932b-5607-4831-b8e7-bb6901375255.img', 'df75f05791de37d9ab9e5681c2419b39'))
#     gs = GlanceService()
#     gs.download('dd69c916-50f4-4849-909a-68ba9bfc7c23', 'test.img')
    