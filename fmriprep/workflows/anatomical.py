from nipype.interfaces.ants import (ApplyTransform,  BrainExtraction, 
    N4BiasFieldCorrection, Registration)
from nipype.pipeline import engine as pe

def t1w_preprocessing(name='t1w_preprocessing'):
    
    inputnode = pe.Node(niu.IdentityInterface(fields=['t1']), name='inputnode')
    
    # T1 Bias Field Correction
    n4 = pe.Node(N4BiasFieldCorrection(dimension=3, bspline_fitting_distance=300,
                                       shrink_factor=3), name="Bias_Field_Correction")
    
    # Skull strip the T1 with ANTS Brain Extraction
    T1_skull_strip = pe.Node(
        BrainExtraction(dimension=3), name="antsreg_T1_Brain_Extraction")
    T1_skull_strip.inputs.brain_template = settings[
        'skull_strip'].get('brain_template', pkgr.resource_filename('fmriprep', 'data/brain_template.nii.gz'))
    T1_skull_strip.inputs.brain_probability_mask = settings[
        'skull_strip'].get('brain_probmask', pkgr.resource_filename('fmriprep', 'data/brain_probmask.nii.gz'))
    T1_skull_strip.inputs.extraction_registration_mask = settings[
        'skull_strip'].get('reg_mask', pkgr.resource_filename('fmriprep', 'data/reg_mask.nii.gz'))
    
    # ANTs registration
    antsreg = pe.Node(Registration(), name="T1_2_MNI_Registration")
    antsreg.inputs.fixed_image = settings['fsl'].get('mni_template', op.join(
        os.getenv('FSLDIR'), 'data/standard/MNI152_T1_2mm_brain.nii.gz'))
    antsreg.inputs.metric = ['Mattes'] * 3 + [['Mattes', 'CC']]
    antsreg.inputs.metric_weight = [1] * 3 + [[0.5, 0.5]]
    antsreg.inputs.dimension = 3
    antsreg.inputs.write_composite_transform = True
    antsreg.inputs.radius_or_number_of_bins = [32] * 3 + [[32, 4]]
    antsreg.inputs.shrink_factors = [[6, 4, 2]] + [[3, 2, 1]]*2 + [[4, 2, 1]]
    antsreg.inputs.smoothing_sigmas = [[4, 2, 1]] * 3 + [[1, 0.5, 0]]
    antsreg.inputs.sigma_units = ['vox'] * 4
    antsreg.inputs.output_transform_prefix = "ANTS_T1_2_MNI"
    antsreg.inputs.transforms = ['Translation', 'Rigid', 'Affine', 'SyN']
    antsreg.inputs.transform_parameters = [
        (0.1,), (0.1,), (0.1,), (0.2, 3.0, 0.0)]
    antsreg.inputs.initial_moving_transform_com = True
    antsreg.inputs.number_of_iterations = ([[10, 10, 10]]*3 + [[1, 5, 3]])
    antsreg.inputs.convergence_threshold = [1.e-8] * 3 + [-0.01]
    antsreg.inputs.convergence_window_size = [20] * 3 + [5]
    antsreg.inputs.sampling_strategy = ['Regular'] * 3 + [[None, None]]
    antsreg.inputs.sampling_percentage = [0.3] * 3 + [[None, None]]
    antsreg.inputs.output_warped_image = True
    antsreg.inputs.use_histogram_matching = [False] * 3 + [True]
    antsreg.inputs.use_estimate_learning_rate_once = [True] * 4
    #antsreg.inputs.interpolation = 'NearestNeighbor'
    
    # Transforming parcels from stan
    at = pe.Node(ApplyTransforms(dimension=3, interpolation='NearestNeighbor',
                                 default_value=0), name="Apply_ANTS_transform_MNI_2_T1")
    at.inputs.input_image = settings['connectivity'].get(
        'parellation', pkgr.resource_filename('fmriprep', 'data/parcellation.nii.gz'))
    
    # fast -o fast_test -N -v
    # ../Preprocessing_test_workflow/_subject_id_S2529LVY1263171/Bias_Field_Correction/sub-S2529LVY1263171_run-1_T1w_corrected.nii.gz
    T1_seg = pe.Node(FAST(no_bias=True), name="T1_Segmentation")
    
    workflow = pe.Workflow(name=name)
    workflow.connect([
        (inputnode, n4, [('t1', 'input_image')]),
        (n4, antsreg, [('output_image', 'moving_image')]),
        (antsreg, at, [('inverse_composite_transform', 'transforms')]),
        (n4, T1_skull_strip, [('output_image', 'anatomical_image')]),
        (n4, T1_seg, [('output_image', 'in_files')]),
    ])
    
    return workflow
