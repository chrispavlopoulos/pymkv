""":class:`~pymkv.MKVTrack` classes are used to represent tracks within an MKV or to be used in an MKV. They can
represent a video, audio, or subtitle track.

Examples
--------
Below are some basic examples of how the :class:`~pymkv.MKVTrack` objects can be used.

Create a new :class:`~pymkv.MKVTrack` from a track file. This example takes a standalone track file and uses it in an
:class:`~pymkv.MKVTrack`.

>>> from pymkv import MKVTrack
>>> track1 = MKVTrack('path/to/track.h264')
>>> track1.track_name = 'Some Name'
>>> track1.language = 'eng'

Create a new :class:`~pymkv.MKVTrack` from an MKV file. This example will take a specific track from an MKV and also
prevent any global tags from being included if the :class:`~pymkv.MKVTrack` is muxed into an :class:`~pymkv.MKVFile`.

>>> track2 = MKVTrack('path/to/track.aac')
>>> track2.language = 'eng'

Create a new :class:`~pymkv.MKVTrack` from an MKV file. This example will take a specific track from an MKV and also
prevent any global tags from being included if the :class:`~pymkv.MKVTrack` is muxed into an :class:`~pymkv.MKVFile`.

>>> track3 = MKVTrack('path/to/MKV.mkv', track_id=1)
>>> track3.no_global_tags = True

Now all these tracks can be added to an :class:`~pymkv.MKVFile` object and muxed together.

>>> from pymkv import MKVFile
>>> file = MKVFile()
>>> file.add_track(track1)
>>> file.add_track(track2)
>>> file.add_track(track3)
>>> file.mux('path/to/output.mkv')
"""

import json
import os.path
from os import devnull
from os.path import expanduser, isfile
import subprocess as sp
from pathlib import Path

from pymkv.TypeTrack import get_track_extension
from pymkv.Verifications import verify_supported
from pymkv.ISO639_2 import is_iso639_2
from pymkv.BCP47 import is_bcp47


class MKVTrack():
    """A class that represents a track for an :class:`~pymkv.MKVFile` object.

    :class:`~pymkv.MKVTrack` objects are video, audio, or subtitles. Tracks can be standalone files or a single track
    within an MKV file, both can be handled by pymkv. An :class:`~pymkv.MKVTrack` object can be added to an
    :class:`~pymkv.MKVFile` and will be included when the MKV is muxed.

    Parameters
    ----------
    file_path : str
        Path to the track file. This can also be an MKV where the `track_id` is the track represented in the MKV.
    track_id : int, optional
        The id of the track to be used from the file. `track_id` only needs to be set when importing a track from
        an MKV. In this case, you can specify `track_id` to indicate which track from the MKV should be used. If not
        set, it will import the first track. Track 0 is imported by default because mkvmerge sees standalone
        track files as having one track with track_id set as 0.
    track_name : str, optional
        The name that will be given to the track when muxed into a file.
    language : str, optional
        The language of the track. It must be an ISO639-2 language code.
    language_ietf : str, optional
        The language of the track. It must be a BCP47 language code. Has priority over 'language'.
    default_track : bool, optional
        Determines if the track should be the default track of its type when muxed into an MKV file.
    forced_track : bool, optional
        Determines if the track should be a forced track when muxed into an MKV file.
    mkvmerge_path : str, optional
        The path where pymkv looks for the mkvmerge executable. pymkv relies on the mkvmerge executable to parse
        files. By default, it is assumed mkvmerge is in your shell's $PATH variable. If it is not, you need to set
        *mkvmerge_path* to the executable location.

    Attributes
    ----------
    mkvmerge_path : str
        The path of the mkvmerge executable.
    track_name : str
        The name that will be given to the track when muxed into a file.
    default_track : bool
        Determines if the track should be the default track of its type when muxed into an MKV file.
    forced_track : bool
        Determines if the track should be a forced track when muxed into an MKV file.
    no_chapters : bool
        If chapters exist in the track file, don't include them when this :class:`~pymkv.MKVTrack` object is a track
        in an :class:`~pymkv.MKVFile` mux operation. This option has no effect on standalone track files, only tracks
        that are already part of an MKV file.
    no_global_tags : bool
        If global tags exist in the track file, don't include them when this :class:`~pymkv.MKVTrack` object is a track
        in an :class:`~pymkv.MKVFile` mux operation. This option has no effect on standalone track files, only tracks
        that are already part of an MKV file.
    no_track_tags : bool
        If track tags exist in the specified track within the track file, don't include them when this
        :class:`~pymkv.MKVTrack` object is a track in an :class:`~pymkv.MKVFile` mux operation. This option has no
        effect on standalone track files, only tracks that are already part of an MKV file.
    no_attachments : bool
        If attachments exist in the track file, don't include them when this :class:`~pymkv.MKVTrack` object is a track
        in an :class:`~pymkv.MKVFile` mux operation. This option has no effect on standalone track files, only tracks
        that are already part of an MKV file.
    """

    def __init__(self, file_path, track_id=0, track_name=None, language=None, language_ietf=None, default_track=False,
                 forced_track=False, flag_commentary=False, flag_hearing_impaired=False, flag_visual_impaired=False,
                 flag_original=False, mkvmerge_path='mkvmerge', mkvextract_path='mkvextract', sync=None):
        # track info
        self._track_codec = None
        self._track_type = None

        # base
        self.mkvmerge_path = mkvmerge_path
        self._file_path = None
        self.file_path = file_path
        self._track_id = None
        self.track_id = track_id
        self._file_id = 0
        self._pts = 0

        # flags
        self.track_name = track_name
        self._language = None
        self.language = language
        self._sync = None
        self.sync = sync
        self._language_ietf = None
        self.language_ietf = language_ietf
        self._tags = None
        self.default_track = default_track
        self.forced_track = forced_track
        self.flag_commentary = flag_commentary
        self.flag_hearing_impaired = flag_hearing_impaired
        self.flag_visual_impaired = flag_visual_impaired
        self.flag_original = flag_original

        # exclusions
        self.no_chapters = False
        self.no_global_tags = False
        self.no_track_tags = False
        self.no_attachments = False

        # mkvextract
        self.mkvextract_path = mkvextract_path
        self.extension = get_track_extension(self)

    def __repr__(self):
        return repr(self.__dict__)

    @property
    def file_path(self):
        """str: The path to the track or MKV file containing the desired track.

        Setting this property will verify the passed in file is supported by mkvmerge and set the track_id to 0. It
        is recommended to recreate MKVTracks instead of setting their file path after instantiation.

        Raises
        ------
        ValueError
            Raised if `file_path` is not a supported file type.
        """
        return self._file_path

    @file_path.setter
    def file_path(self, file_path):
        file_path = expanduser(file_path)
        if not verify_supported(file_path, mkvmerge_path=self.mkvmerge_path):
            raise ValueError('"{}" is not a supported file')
        self._file_path = file_path
        self.track_id = 0

    @property
    def file_id(self):
        """int: The ID of the file the track belongs to.

        The file ID represents which file the current track is associated with. This is particularly useful
        when handling multiple files.

        Raises
        ------
        IndexError
            Raised if the passed in index is out of range of the file's tracks.
        """
        return self._file_id

    @file_id.setter
    def file_id(self, file_id: int):
        if isinstance(file_id, int):
            self._file_id = file_id
        else:
            raise ValueError('file_id must be an integer')

    @property
    def track_id(self):
        """int: The ID of the track within the file.

        Setting *track_id* will check that the ID passed in exists in the file. It will then look at the new track
        and set the codec and track type. Should be left at 0 unless extracting a specific track from an MKV.

        Raises
        ------
        IndexError
            Raised if the passed in index is out of range of the file's tracks.
        """
        return self._track_id

    @track_id.setter
    def track_id(self, track_id):
        info_json = json.loads(sp.check_output([self.mkvmerge_path, '-J', self.file_path]).decode())
        if not 0 <= track_id < len(info_json['tracks']):
            raise IndexError('track index out of range')
        self._track_id = track_id
        try:
            self._pts = info_json['tracks'][track_id]["start_pts"]
        except KeyError:
            self._pts = 0
        self._track_codec = info_json['tracks'][track_id]['codec']
        self._track_type = info_json['tracks'][track_id]['type']

    @property
    def language(self):
        """str: The language of the track.

        Setting this property will verify that the passed in language is an ISO-639 language code and use it as the
        language for the track.

        Raises
        ------
        ValueError
            Raised if the passed in language is not an ISO 639-2 language code.
        """
        return self._language

    @language.setter
    def language(self, language):
        if language is None or is_iso639_2(language):
            self._language = language
        else:
            raise ValueError('not an ISO639-2 language code')

    @property
    def pts(self):
        return self._pts

    @property
    def sync(self):
        """int: track delay.

        Setting this property allows you to wiggle the track negatively/positively.
        """
        return self._sync

    @sync.setter
    def sync(self, sync):
        self._sync = sync

    @property
    def language_ietf(self):
        """str: The language of the track with BCP47 format.
        Setting this property will verify that the passed in language is a BCP47 language code and use it as the
        language for the track.
        Raises
        ------
        ValueError
            Raised if the passed in language is not a BCP47 language code.
        """
        return self._language_ietf

    @language_ietf.setter
    def language_ietf(self, language_ietf): # es-150
        if language_ietf is None or is_bcp47(language_ietf):
            self._language_ietf = language_ietf
        elif (is_bcp47(language_ietf.split('-')[0])):
            self._language_ietf = language_ietf.split('-')[0]
        else:
            raise ValueError('not a BCP47 language code')

    @property
    def tags(self):
        """str: The tags file to include with the track.

        Setting this property will check that the file path passed in exists and set it as the tags file.

        Raises
        ------
        FileNotFoundError
            Raised if the passed in file does not exist or is not a file.
        TypeError
            Raises if the passed in file is not of type str.
        """
        return self._tags

    @tags.setter
    def tags(self, file_path):
        if not isinstance(file_path, str):
            raise TypeError(f'"{file_path}" is not of type str')
        file_path = expanduser(file_path)
        if not isfile(file_path):
            raise FileNotFoundError(f'"{file_path}" does not exist')
        self._tags = file_path

    @property
    def track_codec(self):
        """str: The codec of the track such as h264 or AAC."""
        return self._track_codec

    @property
    def track_type(self):
        """str: The type of track such as video or audio."""
        return self._track_type

    def extract(self, output_directory: str = None, output_filename = None, silent: bool = False) -> str:
        """Extract the track as a file.

        Parameters
        ----------
        output_path : str
            The path to be used as the output file in the mkvextract command.
        silent : bool, optional
            By default the mkvmerge output will be shown unless silent is True.
        """
        extract_info_file = f"_[{self.track_id}]"
        if self.language:
            extract_info_file += f"_{self.language}"
        if self.extension:
            extract_info_file += f".{self.extension}"
        if (not self.language and not self.expansion) and self.track_name:
            extract_info_file += f"_{self.track_name}"

        if output_directory is None:
            output_directory = self.file_path

        if output_filename is None:
            mkv_filename = Path(self.file_path).name
            output_filename = f"{mkv_filename}{extract_info_file}"

        output_path = expanduser(os.path.join(output_directory, output_filename))
        
        command = [self.mkvextract_path, 'tracks', f'{self.file_path}', f'{self.track_id}:{output_path}']
        try:
            if silent:
                sp.run(command, stdout=open(devnull, 'wb'), check=True)
            else:
                print('Running with command:\n"' + " ".join(command) + '"')
                sp.run(command, check=True, capture_output=True)
        except sp.CalledProcessError as err:
            message = err.output.decode('utf-8')
            print(message)

        return output_path
