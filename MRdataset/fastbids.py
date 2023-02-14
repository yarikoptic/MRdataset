from pathlib import Path

from MRdataset.base import BaseDataset, Run, Modality, Subject, Session
from MRdataset.config import VALID_BIDS_EXTENSIONS
from MRdataset.utils import select_parameters, files_under_folder, get_ext


# TODO: check what if each variable is None. Apply try catch
class FastBIDSDataset(BaseDataset):
    """
    Container to manage the properties and methods of a BIDS dataset downloaded
    from OpenNeuro. In contrast to BIDSDataset, it doesn't create a BIDSLayout
    object for the dataset. Instead, it uses the file structure to extract
    information about the dataset. Therefore, it is much faster than
    BIDSDataset.
    """

    def __init__(self,
                 name='mind',
                 data_source=None,
                 include_nifti_header=False,
                 is_complete=True,
                 **_kwargs):

        """
        Parameters
        ----------
        name : str
            an identifier/name for the dataset
        data_source : Path or str
            directory containing dicom files, supports nested hierarchies
        metadata_source : str or Path
            directory to store cache
        include_nifti_header :
            whether to check nifti headers for compliance,
            only used when --style==bids
        Examples
        --------
        >>> from MRdataset.fastbids import FastBIDSDataset
        >>> dataset = FastBIDSDataset()
        """

        super().__init__(data_source)

        self.is_complete = is_complete
        self.include_nifti_header = include_nifti_header

    def walk(self):
        """
        Retrieves filenames in the directory tree, verifies if it is json
        file, extracts relevant parameters and stores it in project. Creates
        a desirable hierarchy for a neuroimaging experiment
        """
        # TODO: Need to handle BIDS datasets without JSON files
        for file in files_under_folder(self.data_source):
            ext = get_ext(file)
            if ext in VALID_BIDS_EXTENSIONS:
                self.read_single(file)
        if not self.modalities:
            raise ValueError("Expected Sidecar JSON files in --data_source. Got 0")

    def read_single(self, file):
        datatype = file.parent.name
        modality_obj = self.get_modality_by_name(datatype)
        if modality_obj is None:
            modality_obj = Modality(datatype)
        nSub = file.parents[2].name
        subject_obj = modality_obj.get_subject_by_name(nSub)
        if subject_obj is None:
            subject_obj = Subject(nSub)
        nSess = file.parents[1].name
        session_node = subject_obj.get_session_by_name(nSess)
        if session_node is None:
            session_node = Session(nSess)
            session_node = self.parse(session_node,
                                      file)
            if session_node.runs:
                subject_obj.add_session(session_node)
            if subject_obj.sessions:
                modality_obj.add_subject(subject_obj)
        if modality_obj.subjects:
            self.add_modality(modality_obj)

    def parse(self, session_node: Session, filepath: Path) -> Session:
        """
            Extracts parameters for a file. Adds the parameters as a
            new run node to given session node, returns modified session node.

            Parameters
            ----------
            filepath : Path
                path to the file
            session_node : MRdataset.base.Session
                session node to which the run node has to be added

            Returns
            -------
            session_node : MRdataset.base.Session
                modified session_node which also contains the new run
            """

        filename = filepath.stem
        params_from_file = dict()
        filepath = filepath.parent / (filepath.stem + '.json')
        if filepath.is_file():
            params_from_file.update(select_parameters(filepath))

        if self.include_nifti_header:
            filepath = filepath.parent/(filepath.stem+'.nii')
            if filepath.is_file():
                params_from_file.update(select_parameters(filepath))

            filepath = filepath.parent / (filepath.stem + '.nii.gz')
            if filepath.is_file():
                params_from_file.update(select_parameters(filepath))

        if params_from_file:
            run_node = session_node.get_run_by_name(filename)
            if run_node is None:
                run_node = Run(filename)
            for k, v in params_from_file.items():
                run_node.params[k] = v
            run_node.echo_time = params_from_file.get('EchoTime', 1.0)
            session_node.add_run(run_node)
        return session_node

