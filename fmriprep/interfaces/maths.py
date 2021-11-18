import os
from nipype.interfaces.base import SimpleInterface, TraitedSpec, traits, File
from nipype.utils.filemanip import fname_presuffix


class ThresholdInputSpec(TraitedSpec):
    in_file = File(exists=True, mandatory=True, desc="Input imaging file")
    out_file = File(desc="Output file name")
    threshold = traits.Float(0., usedefault=True, desc="Values under this become 0")


class ThresholdOutputSpec(TraitedSpec):
    out_file = File(desc="Output file name")


class Threshold(SimpleInterface):
    """ Simple thresholding interface that sets values below the threshold to 0

    If no values are below the threshold, nothing is done and the in_file is passed
    as the out_file without copying.
    """
    input_spec = ThresholdInputSpec
    output_spec = ThresholdOutputSpec

    def _run_interface(self, runtime):
        import nibabel as nb
        img = nb.load(self.inputs.in_file)
        data = img.get_fdata()
        subthresh = data < self.inputs.threshold

        out_file = self.inputs.out_file
        if out_file:
            out_file = os.path.join(runtime.cwd, out_file)

        if subthresh.any():
            data[subthresh] = 0
            if not out_file:
                out_file = fname_presuffix(self.inputs.in_file, suffix="_thr", newpath=runtime.cwd)
            img.__class__(data, img.affine, img.header).to_filename(out_file)
        elif not out_file:
            out_file = self.inputs.in_file

        self._results["out_file"] = out_file
        return runtime
