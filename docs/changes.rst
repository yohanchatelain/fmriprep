.. include:: links.rst

-----------------------------------
*fMRIPrep*'s versioning and changes
-----------------------------------
*fMRIPrep* follows the `NiPreps conventions <https://www.nipreps.org/devs/releases/>`__
for the versioning scheme.
In short, the basic release form is ``YY.MINOR.PATCH``, so the first release of
2020 was 20.0.0.
The most relevant implication to the user is that compatibility of intermediate and
final results is guaranteed through a given series (in other words, ``YY.MINOR``).
For instance, version 20.1.4 must be compatible with processing done with 20.1.0.

**Long-term support (LTS) releases**.
Some releases marked as LTS are special and have a `longer support window
<https://www.nipreps.org/devs/releases/#long-term-support-series>`__.

**Release codenames**.
Release series (``YY.MINOR``) share a common *codename*.
The codename will be one name drawn from `Wikipedia's list of women neuroscientists
<https://en.wikipedia.org/wiki/List_of_women_neuroscientists>`__.
This convention was initiated with the 21.0.x «*Kreek*» series, which are named after
`Mary Jeanne Kreek (1937-2021) <https://en.wikipedia.org/wiki/Mary_Jeanne_Kreek>`__.
Before this convention was set with 21.0 *Kreek*, only
`fMRIPrep 1.0 <https://github.com/nipreps/fmriprep/releases/tag/1.0.0>`__ —
the first official release — had a codename (*BOLD raccoon*).

What's new
----------

.. include:: ../CHANGES.rst
