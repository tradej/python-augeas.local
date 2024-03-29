"""Pure python bindings for the augeas library

Augeas is a library for programmatically editing configuration files.
Augeas parses configuration files into a tree structure, which it exposes
through its public API. Changes made through the API are written back to
the initially read files.

The transformation works very hard to preserve comments and formatting
details. It is controlled by ``lens'' definitions that describe the file
format and the transformation into a tree.

"""

#
# Copyright (C) 2008 Nathaniel McCallum
# Copyright (C) 2008 Jeff Schroeder <jeffschroeder@computer.org>
# Copyright (C) 2009 Red Hat, Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307  USA
#
# Author: Nathaniel McCallum <nathaniel@natemccallum.com>

__author__ = "Nathaniel McCallum <nathaniel@natemccallum.com>"
__credits__ = """Jeff Schroeder <jeffschroeder@computer.org>
Harald Hoyer <harald@redhat.com> - initial python bindings, packaging
Nils Philippsen <nils@redhat.com>
"""

import ctypes
import ctypes.util
import six
import sysconfig
from functools import reduce
from sys import version_info as _pyver

def _dlopen(*args):
    """Search for one of the libraries given as arguments and load it.
    Returns the library.
    """
    libs = [l for l in [ ctypes.util.find_library(a) for a in args ] if l]
    lib  = reduce(lambda x, y: x or ctypes.cdll.LoadLibrary(y), libs, None)
    if not lib:
        raise ImportError("Unable to import lib%s!" % args[0])
    return lib

class Augeas(object):
    "Class wrapper for the augeas library"

    # Load libpython (for 'PyFile_AsFile()' and 'PyMem_Free()')
    # pylint: disable-msg=W0142
    _libpython = ctypes.cdll.LoadLibrary(sysconfig.get_config_var('INSTSONAME'))
    if not six.PY3:
        _libpython.PyFile_AsFile.restype = ctypes.c_void_p

    # Load libaugeas
    _libaugeas = _dlopen("augeas")
    _libaugeas.aug_init.restype = ctypes.c_void_p

    # Augeas Flags
    NONE = 0
    SAVE_BACKUP = 1 << 0
    SAVE_NEWFILE = 1 << 1
    TYPE_CHECK = 1 << 2
    NO_STDINC = 1 << 3
    SAVE_NOOP = 1 << 4
    NO_LOAD = 1 << 5
    NO_MODL_AUTOLOAD = 1 << 6
    ENABLE_SPAN = 1 << 7

    def __init__(self, root=None, loadpath=None, flags=NONE):
        """Initialize the library.

        Use 'root' as the filesystem root. If 'root' is None, use the value of
        the environment variable AUGEAS_ROOT. If that doesn't exist either,
        use "/".

        'loadpath' is a colon-spearated list of directories that modules
        should be searched in. This is in addition to the standard load path
        and the directories in AUGEAS_LENS_LIB.

        'flags' is a bitmask made up of values from AUG_FLAGS."""

        # Sanity checks
        if not isinstance(root, six.string_types) and root is not None:
            raise TypeError("root MUST be a string or None!")
        if not isinstance(loadpath, six.string_types) and loadpath is not None:
            raise TypeError("loadpath MUST be a string or None!")
        if not isinstance(flags, int):
            raise TypeError("flag MUST be a flag!")

        # Encoding for Python 3
        safe_root = root if (not six.PY3 or root is None) else root.encode('utf-8')
        safe_loadpath = loadpath if (not six.PY3 or loadpath is None) else loadpath.encode('utf-8')

        # Create the Augeas object
        self.__handle = Augeas._libaugeas.aug_init(safe_root, safe_loadpath, flags)
        if not self.__handle:
            raise RuntimeError("Unable to create Augeas object!")
        # Make sure self.__handle is a void*, not an integer
        self.__handle = ctypes.c_void_p(self.__handle)

    def __del__(self):
        self.close()

    def get(self, path):
        """Lookup the value associated with 'path'.
        Returns the value at the path specified.
        It is an error if more than one node matches 'path'."""

        # Sanity checks
        if not isinstance(path, six.string_types):
            raise TypeError("path MUST be a string!")
        if not self.__handle:
            raise RuntimeError("The Augeas object has already been closed!")

        # Create the char * value
        value = ctypes.c_char_p()

        # Encoding for Python 3
        safe_path = path if not six.PY3 else path.encode('utf-8')

        # Call the function and pass value by reference (char **)
        ret = Augeas._libaugeas.aug_get(self.__handle, safe_path,
                                        ctypes.byref(value))
        if ret > 1:
            raise ValueError("path specified had too many matches!")

        if not six.PY3 or not isinstance(value.value, bytes):
            return value.value
        else:
            return value.value.decode('utf-8')

    def set(self, path, value):
        """Set the value associated with 'path' to 'value'.
        Intermediate entries are created if they don't exist.
        It is an error if more than one node matches 'path'."""

        # Sanity checks
        if not isinstance(path, six.string_types):
            raise TypeError("path MUST be a string!")
        if not isinstance(value, six.string_types) and value is not None:
            raise TypeError("value MUST be a string or None!")
        if not self.__handle:
            raise RuntimeError("The Augeas object has already been closed!")

        # Encoding for Python 3
        safe_path = path if not six.PY3 else path.encode('utf-8')
        safe_value = value if not six.PY3 else value.encode('utf-8')

        # Call the function
        ret = Augeas._libaugeas.aug_set(self.__handle, safe_path, safe_value)
        if ret != 0:
            raise ValueError("Unable to set value to path!")

    def setm(self, base, sub, value):
        """Set the value of multiple nodes in one operation.
        Find or create a node matching 'sub' by interpreting 'sub'
        as a path expression relative to each node matching 'base'.
        'sub' may be None, in which case all the nodes matching
        'base' will be modified."""

        # Sanity checks
        if type(base) != str:
            raise TypeError("base MUST be a string!")
        if type(sub) != str and sub is not None:
            raise TypeError("sub MUST be a string or None!")
        if type(value) != str:
            raise TypeError("value MUST be a string!")
        if not self.__handle:
            raise RuntimeError("The Augeas object has already been closed!")

        # Encoding for Python 3
        safe_base = base if not six.PY3 else base.encode('utf-8')
        safe_sub = sub if not six.PY3 else sub.encode('utf-8')
        safe_value = value if not six.PY3 else value.encode('utf-8')

        # Call the function
        ret = Augeas._libaugeas.aug_setm(self.__handle, safe_base, safe_sub, safe_value)
        if ret < 0:
            raise ValueError("Unable to set value to path!")
        return ret

    def defvar(self, name, expr):
        """Define a variable 'name' whose value is the result of
        evaluating 'expr'. If a variable 'name' already exists, its
        name will be replaced with the result of evaluating 'expr'.
 
        If 'expr' is None, the variable 'name' will be removed if it
        is defined.
 
        Path variables can be used in path expressions later on by
        prefixing them with '$'."""

        # Sanity checks
        if type(name) != str:
            raise TypeError("name MUST be a string!")
        if type(expr) != str and expr is not None:
            raise TypeError("expr MUST be a string or None!")
        if not self.__handle:
            raise RuntimeError("The Augeas object has already been closed!")

        # Encoding for Python 3
        safe_name = name if not six.PY3 else name.encode('utf-8')
        safe_expr = expr if not six.PY3 else expr.encode('utf-8')

        # Call the function
        ret = Augeas._libaugeas.aug_defvar(self.__handle, safe_name, safe_expr)
        if ret < 0:
            raise ValueError("Unable to register variable!")
        return ret

    def defnode(self, name, expr, value):
        """Define a variable 'name' whose value is the result of
        evaluating 'expr', which must not be None and evaluate to a
        nodeset. If a variable 'name' already exists, its name will
        be replaced with the result of evaluating 'expr'.
 
        If 'expr' evaluates to an empty nodeset, a node is created,
        equivalent to calling set(expr, value) and 'name' will be the
        nodeset containing that single node."""

        # Sanity checks
        if type(name) != str:
            raise TypeError("name MUST be a string!")
        if type(expr) != str:
            raise TypeError("expr MUST be a string!")
        if type(value) != str:
            raise TypeError("value MUST be a string!")
        if not self.__handle:
            raise RuntimeError("The Augeas object has already been closed!")

        # Encoding for Python 3
        safe_name = name if not six.PY3 else name.encode('utf-8')
        safe_expr = expr if not six.PY3 else expr.encode('utf-8')
        safe_value = value if not six.PY3 else value.encode('utf-8')

        # Call the function
        ret = Augeas._libaugeas.aug_defnode(self.__handle, safe_name,\
                                            safe_expr, safe_value, None)
        if ret < 0:
            raise ValueError("Unable to register node!")
        return ret

    def move(self, src, dst):
        """Move the node 'src' to 'dst'. 'src' must match exactly one node
           in the tree. 'dst' must either match exactly one node in the
           tree, or may not exist yet. If 'dst' exists already, it and all
           its descendants are deleted before moving 'src' there. If 'dst'
           does not exist yet, it and all its missing ancestors are created."""

        # Sanity checks
        if not isinstance(src, six.string_types):
            raise TypeError("src MUST be a string!")
        if not isinstance(dst, six.string_types):
            raise TypeError("dst MUST be a string!")
        if not self.__handle:
            raise RuntimeError("The Augeas object has already been closed!")

        # Encoding for Python 3
        safe_src = src if not six.PY3 else src.encode('utf-8')
        safe_dst = dst if not six.PY3 else dst.encode('utf-8')

        # Call the function
        ret = Augeas._libaugeas.aug_mv(self.__handle, safe_src, safe_dst)
        if ret != 0:
            raise ValueError("Unable to move src to dst!")

    def insert(self, path, label, before=True):
        """Create a new sibling 'label' for 'path' by inserting into the tree
        just before 'path' (if 'before' is True) or just after 'path'
        (if 'before' is False).

        'path' must match exactly one existing node in the tree, and 'label'
        must be a label, i.e. not contain a '/', '*' or end with a bracketed
        index '[N]'."""

        # Sanity checks
        if not isinstance(path, six.string_types):
            raise TypeError("path MUST be a string!")
        if not isinstance(label, six.string_types):
            raise TypeError("label MUST be a string!")
        if not self.__handle:
            raise RuntimeError("The Augeas object has already been closed!")

        # Encoding for Python 3
        safe_path = path if not six.PY3 else path.encode('utf-8')
        safe_label = label if not six.PY3 else label.encode('utf-8')

        # Call the function
        ret = Augeas._libaugeas.aug_insert(self.__handle, safe_path,
                                           safe_label, before and 1 or 0)
        if ret != 0:
            raise ValueError("Unable to insert label!")

    def remove(self, path):
        """Remove 'path' and all its children. Returns the number of entries
        removed. All nodes that match 'path', and their descendants, are
        removed."""

        # Sanity checks
        if not isinstance(path, six.string_types):
            raise TypeError("path MUST be a string!")
        if not self.__handle:
            raise RuntimeError("The Augeas object has already been closed!")

        # Encoding for Python 3
        safe_path = path if not six.PY3 else path.encode('utf-8')

        # Call the function
        return Augeas._libaugeas.aug_rm(self.__handle, safe_path)

    def match(self, path):
        """Return the matches of the path expression 'path'. The returned paths
        are sufficiently qualified to make sure that they match exactly one
        node in the current tree.

        Path expressions use a very simple subset of XPath: the path 'path'
        consists of a number of segments, separated by '/'; each segment can
        either be a '*', matching any tree node, or a string, optionally
        followed by an index in brackets, matching tree nodes labelled with
        exactly that string. If no index is specified, the expression matches
        all nodes with that label; the index can be a positive number N, which
        matches exactly the Nth node with that label (counting from 1), or the
        special expression 'last()' which matches the last node with the given
        label. All matches are done in fixed positions in the tree, and nothing
        matches more than one path segment."""

        # Sanity checks
        if not isinstance(path, six.string_types):
            raise TypeError("path MUST be a string!")
        if not self.__handle:
            raise RuntimeError("The Augeas object has already been closed!")

        # Encoding for Python 3
        safe_path = path if not six.PY3 else path.encode('utf-8')

        # Create a void ** (this is so python won't mangle the char **,
        # when we free it)
        array = ctypes.POINTER(ctypes.c_void_p)()

        # Call the function and pass the void ** by reference (void ***)
        ret = Augeas._libaugeas.aug_match(self.__handle, safe_path,
                                          ctypes.byref(array))
        if ret < 0:
            raise RuntimeError("Error during match procedure!")

        # Loop through the string array
        matches = []
        for i in range(ret):
            if array[i]:
                # Create a python string and append it to our matches list
                value = ctypes.cast(array[i], ctypes.c_char_p).value
                matches.append(str(value) if not six.PY3 else value.decode('utf-8'))

                # Free the string at this point in the array
                # Wrap the string as a void* as it was not allocated by Python
                Augeas._libpython.PyMem_Free(ctypes.c_void_p(array[i]))

        # Free the array itself
        Augeas._libpython.PyMem_Free(array)

        return matches

    def span(self, path):
        """Get the span according to input file of the node associated with
        PATH. If the node is associated with a file, un tuple of 5 elements is
        returned: (filename, label_start, label_end, value_start, value_end,
        span_start, span_end). If the node associated with PATH doesn't
        belong to a file or is doesn't exists, ValueError is raised."""

        # Sanity checks
        if not isinstance(path, six.string_types):
            raise TypeError("path MUST be a string!")
        if not self.__handle:
            raise RuntimeError("The Augeas object has already been closed!")

        # Encoding for Python 3
        safe_path = path if not six.PY3 else path.encode('utf-8')

        filename = ctypes.c_char_p()
        label_start = ctypes.c_uint()
        label_end = ctypes.c_uint()
        value_start = ctypes.c_uint()
        value_end = ctypes.c_uint()
        span_start = ctypes.c_uint()
        span_end = ctypes.c_uint()

        r = ctypes.byref

        ret = Augeas._libaugeas.aug_span(self.__handle, safe_path, r(filename),
                                         r(label_start), r(label_end),
                                         r(value_start), r(value_end),
                                         r(span_start), r(span_end))
        if (ret < 0):
            raise ValueError("Error during span procedure")

        return (filename.value if not six.PY3 else filename.value.decode('utf-8'),
                label_start.value, label_end.value,
                value_start.value, value_end.value,
                span_start.value, span_end.value)

    def save(self):
        """Write all pending changes to disk. Only files that had any changes
        made to them are written.

        If SAVE_NEWFILE is set in the creation 'flags', create changed files as
        new files with the extension ".augnew", and leave the original file
        unmodified.

        Otherwise, if SAVE_BACKUP is set in the creation 'flags', move the
        original file to a new file with extension ".augsave".

        If neither of these flags is set, overwrite the original file."""

        # Sanity checks
        if not self.__handle:
            raise RuntimeError("The Augeas object has already been closed!")

        # Call the function
        ret = Augeas._libaugeas.aug_save(self.__handle)
        if ret != 0:
            raise IOError("Unable to save to file!")

    def load(self):
        """Load files into the tree. Which files to load and what lenses to use
        on them is specified under /augeas/load in the tree; each entry
        /augeas/load/NAME specifies a 'transform', by having itself exactly one
        child 'lens' and any number of children labelled 'incl' and 'excl'. The
        value of NAME has no meaning.

        The 'lens' grandchild of /augeas/load specifies which lens to use, and
        can either be the fully qualified name of a lens 'Module.lens' or
        '@Module'. The latter form means that the lens from the transform
        marked for autoloading in MODULE should be used.

        The 'incl' and 'excl' grandchildren of /augeas/load indicate which
        files to transform. Their value are used as glob patterns. Any file
        that matches at least one 'incl' pattern and no 'excl' pattern is
        transformed. The order of 'incl' and 'excl' entries is irrelevant.

        When AUG_INIT is first called, it populates /augeas/load with the
        transforms marked for autoloading in all the modules it finds.

        Before loading any files, AUG_LOAD will remove everything underneath
        /augeas/files and /files, regardless of whether any entries have been
        modified or not."""

        # Sanity checks
        if not self.__handle:
            raise RuntimeError("The Augeas object has already been closed!")

        ret = Augeas._libaugeas.aug_load(self.__handle)
        if ret != 0:
            raise RuntimeError("aug_load() failed!")

    def clear_transforms(self):
        """Clear all transforms beneath /augeas/load. If load() is called right
        after this, there will be no files beneath /files."""
        self.remove("/augeas/load/*")

    def add_transform(self, lens, incl, name=None, excl=()):
        """Add a transform beneath /augeas/load.

        lens: the (file)name of the lens to use
        incl: one or more glob patterns for the files to transform
        name: a unique name; use the module name of the lens if omitted
        excl: zero or more glob patterns of files to exclude from transforming
        """

        if not name:
            name = lens.split(".")[0].replace("@", "", 1)
        if type(incl) in six.string_types:
            incl = [incl]
        if type(excl) in six.string_types:
            excl = [excl]

        xfm = "/augeas/load/%s/" % name
        self.set (xfm + "lens", lens)
        for i in range(len(incl)):
            self.set(xfm + "incl[%d]" % (i+1), incl[i])
        for i in range(len(excl)):
            self.set(xfm + "excl[%d]" % (i+1), excl[i])

    def close(self):
        """Close this Augeas instance and free any storage associated with it.
        After this call, this Augeas instance is invalid and can not be used
        for any more operations."""

        # If we are already closed, return
        if not self.__handle:
            return

        # Call the function
        Augeas._libaugeas.aug_close(self.__handle)

        # Mark the object as closed
        self.__handle = None

# for backwards compatibility
# pylint: disable-msg=C0103
class augeas(Augeas):
    "Compat class, obsolete. Use class Augeas directly."

    def __init__(self, *p, **k):
        import warnings
        warnings.warn("use Augeas instead of augeas", DeprecationWarning,
                stacklevel=2)
        super(augeas, self).__init__(*p, **k)
