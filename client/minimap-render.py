#!/usr/bin/env python
#-*- coding:utf-8 -*-

import sys
import os
import subprocess
import tempfile
import re


class MinimapRenderer(object):

    MAP_RE = re.compile(r'^\d{3}-\d{1}(\.tmx)?$')
    PROGRAMS = {
        'default': {
            'tmxrasterizer': 'tmxrasterizer',
            'im_convert': 'convert',
        },
        'win32': {
            'tmxrasterizer': 'tmxrasterizer.exe',
            'im_convert': 'convert.exe',
        },
    }

    def __init__(self, map_name, scale):
        self.map_name = map_name
        self.scale = scale

    def render(self):
        """
            Processes a map
        """
        if not MinimapRenderer.MAP_RE.match(self.map_name):
            sys.stderr.write(u'Invalid map name: %s. Skipping.\n' % self.map_name)
            return 1
        if not self.map_name.endswith(u'.tmx'):
            self.map_name = self.map_name+u'.tmx'

        map_number = os.path.splitext(os.path.basename(self.map_name))[0]
        tmx_file = os.path.normpath(os.path.join(os.getcwdu(), u'..', u'maps', self.map_name))
        minimap_file = os.path.normpath(os.path.join(os.getcwdu(), u'..', u'graphics', u'minimaps', map_number+u'.png'))

        prefix = os.path.commonprefix((tmx_file, minimap_file))
        sys.stdout.write(u'%s -> %s\n' % (os.path.relpath(tmx_file, prefix), os.path.relpath(minimap_file, prefix)))

        try:
            self.do_render(tmx_file, minimap_file)
        except Exception as e:
            sys.stderr.write(u'\x1b[31m\x1b[1mError while rendering %s: %s\x1b[0m\n' % (self.map_name, e))
            return 1
        else:
            return 0

    def do_render(self, tmx_file, bitmap_file):
        """
            The map rendering implementation
        """
        platform_programs = MinimapRenderer.PROGRAMS.get(sys.platform, MinimapRenderer.PROGRAMS.get('default'))
        # tmx rasterize
        mrf, map_raster = tempfile.mkstemp(suffix='.png')
        subprocess.check_call([platform_programs.get('tmxrasterizer'), '--scale', str(self.scale), tmx_file, map_raster])
        if os.stat(map_raster).st_size == 0:
            # the image couldnt be rendered. The most probable reason is
            # that the map was too big (e.g 024-4, 500x500 tiles)
            raise Exception('Map too large to be rendered.')
        # add cell-shading to the minimap to improve readability
        ebf, edges_bitmap = tempfile.mkstemp(suffix='.png')
        subprocess.check_call([
            platform_programs.get('im_convert'), map_raster,
            '-set', 'option:convolve:scale', '-1!',
            '-morphology', 'Convolve', 'Laplacian:0',
            '-colorspace', 'gray',
            '-auto-level',
            '-threshold', '2.8%',
            '-negate',
            '-transparent', 'white',
            edges_bitmap
        ])
        subprocess.check_call([
            platform_programs.get('im_convert'), map_raster, edges_bitmap,
            '-compose', 'Dissolve',
            '-define', 'compose:args=35',
            '-composite',
            bitmap_file
        ])
        os.unlink(map_raster)
        os.unlink(edges_bitmap)

    @staticmethod
    def check_programs():
        """
            Checks the require programs are available
        """
        def which(program):
            import os
            def is_exe(fpath):
                return os.path.isfile(fpath) and os.access(fpath, os.X_OK)
            fpath, fname = os.path.split(program)
            if fpath:
                if is_exe(program):
                    return program
            else:
                for path in os.environ["PATH"].split(os.pathsep):
                    exe_file = os.path.join(path, program)
                    if is_exe(exe_file):
                        return exe_file
            return None

        platform_programs = MinimapRenderer.PROGRAMS.get(sys.platform, MinimapRenderer.PROGRAMS.get('default'))
        for program in platform_programs.values():
            if not which(program):
                raise Exception('The required "%s" program is missing from your PATH.' % program)

def usage():
    sys.stderr.write(u'''Usage: %s MAP_NAME...

    Example:
        $ ./minimap-render.py 007-1
    will render the map at maps/007-1.tmx in the graphics/minimaps directory.

    For convenience,
        $ ./minimap-render.py 007-1.tmx
    is also acceptable, for e.g running things like,
        $ ./minimap-render.py $(ls ../maps/)
    that would render all existing maps.
    \n''' % sys.argv[0])

def main():
    if not len(sys.argv) > 1:
        usage()
        return 127
    if not os.path.basename(os.path.dirname(os.getcwdu())) == u'client-data':
        sys.stderr.write(u'This script must be run from client-data/tools.\n')
        return 1
    try:
        MinimapRenderer.check_programs()
    except Exception as e:
        sys.stderr.write(u'%s\n' % e)
        return 126

    status = 0
    for map_name in sys.argv[1:]:
        map_renderer = MinimapRenderer(map_name, 0.03125) # this scale renders 1px for a tile of 32px
        status += map_renderer.render()
    return status

if __name__ == '__main__':
    sys.exit(main())