"""Module containing the actual commands stapler understands."""

from __future__ import print_function
import math
import os
import itertools

from PyPDF2 import PdfFileWriter

from . import CommandError, iohelper
import staplelib


def round_robin_list(iterables):
    """
        roundrobinLIST(['ABC', 'D', 'EF']) --> A D E B F C
    """
    # Recipe credited to George Sakkis
    pending = len(iterables)
    cycled_iterables = itertools.cycle(iter(it) for it in iterables)
    while pending:
        try:
            for it in cycled_iterables:
                yield next(it)
        except StopIteration:
            pending -= 1
            cycled_iterables = itertools.cycle(itertools.islice(cycled_iterables, pending))


def zip_pdfs(args):
    """Combine 2 files with interleaved pages."""

    filesandranges = iohelper.parse_ranges(args[:-1])
    outputfilename = args[-1]
    verbose = staplelib.OPTIONS.verbose

    if not filesandranges or not outputfilename:
        raise CommandError("Both input and output filenames are required.")

    try:
        filestozip = []
        for input_args in filesandranges:
            pdf = input_args['pdf']
            if verbose:
                print(input_args['name'])

            # empty range means "include all pages"
            pagerange = input_args['pages'] or [
                (p, iohelper.ROTATION_NONE) for p in
                range(1, pdf.getNumPages() + 1)]

            pagestozip = []
            for pageno, rotate in pagerange:
                if 1 <= pageno <= pdf.getNumPages():
                    if verbose:
                        print("Using page: {} (rotation: {} deg.)".format(
                            pageno, rotate))

                    pagestozip.append(pdf.getPage(pageno-1)
                                      .rotateClockwise(rotate))
                else:
                    raise CommandError("Page {} not found in {}.".format(
                        pageno, input_args['name']))
            filestozip.append(pagestozip)

        output = PdfFileWriter()
        for page in list(round_robin_list(filestozip)):
            output.addPage(page)

    except Exception as e:
        raise CommandError(e)

    if os.path.isabs(outputfilename):
        iohelper.write_pdf(output, outputfilename)
    else:
        iohelper.write_pdf(output, staplelib.OPTIONS.destdir +
                           os.sep + outputfilename)


def select(args, inverse=False):
    """
    Concatenate files / select pages from files.

    inverse=True excludes rather than includes the selected pages from
    the file.
    """

    filesandranges = iohelper.parse_ranges(args[:-1])
    outputfilename = args[-1]
    verbose = staplelib.OPTIONS.verbose

    if not filesandranges or not outputfilename:
        raise CommandError("Both input and output filenames are required.")
    iohelper.check_output_file(outputfilename)

    output = PdfFileWriter()
    try:
        for input_args in filesandranges:
            pdf = input_args['pdf']
            if verbose:
                print(input_args['name'])

            # empty range means "include all pages"
            if not inverse:
                pagerange = input_args['pages'] or [
                    (p, iohelper.ROTATION_NONE) for p in
                    range(1, pdf.getNumPages() + 1)]
            else:
                excluded = [p for p, r in input_args['pages']]
                pagerange = [(p, iohelper.ROTATION_NONE) for p in
                             range(1, pdf.getNumPages() + 1) if
                             p not in excluded]

            for pageno, rotate in pagerange:
                if 1 <= pageno <= pdf.getNumPages():
                    if verbose:
                        print("Using page: {} (rotation: {} deg.)".format(
                            pageno, rotate))

                    output.addPage(pdf.getPage(pageno-1)
                                   .rotateClockwise(rotate))
                else:
                    raise CommandError("Page {} not found in {}.".format(
                        pageno, input_args['name']))

    except Exception as e:
        raise CommandError(e)

    if os.path.isabs(outputfilename):
        iohelper.write_pdf(output, outputfilename)
    else:
        iohelper.write_pdf(output, staplelib.OPTIONS.destdir + 
                           os.sep + outputfilename)


def delete(args):
    """Concatenate files and remove pages from files."""

    return select(args, inverse=True)


def split(args):
    """Burst an input file into one file per page."""

    files = iohelper.expand_input_files(args)
    verbose = staplelib.OPTIONS.verbose

    if not files:
        raise CommandError("No input files specified.")

    inputs = []
    try:
        for f in files:
            inputs.append(iohelper.read_pdf(f))
    except Exception as e:
        raise CommandError(e)

    filecount = 0
    pagecount = 0
    for input_file in inputs:
        # zero-padded output file name
        (base, ext) = os.path.splitext(os.path.basename(files[filecount]))
        output_template = ''.join([
            base, 
            '_',
            '%0', 
            str(math.ceil(math.log10(input_file.getNumPages()))),
            'd',
            ext
        ])

        for pageno in range(input_file.getNumPages()):
            output = PdfFileWriter()
            output.addPage(input_file.getPage(pageno))

            outputname = output_template % (pageno + 1)
            if verbose:
                print(outputname)
            iohelper.write_pdf(output, staplelib.OPTIONS.destdir + 
                               os.sep + outputname)
            pagecount += 1
        filecount += 1

    if verbose:
        print("\n{} page(s) in {} file(s) processed.".format(
            pagecount, filecount))


def info(args):
    """Display Metadata content for all input files."""
    files = iohelper.expand_input_files(args)

    if not files:
        raise CommandError("No input files specified.")

    for f in files:
        pdf = iohelper.read_pdf(f)
        print("*** Metadata for {}".format(f))
        print()
        doc_info = pdf.documentInfo
        if doc_info:
            for name, value in doc_info.items():
                print(u"    {}:  {}".format(name, value))
        else:
            print("    (No metadata found.)")
        print()
