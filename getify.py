import os.path
import shutil
import sys
import urllib.request
import uuid
import zipfile

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from bs4 import BeautifulSoup


def find_between(file):
    f = open(file, "r", encoding="utf8")
    soup = BeautifulSoup(f, 'html.parser')
    return soup.title.string


"""Downloads web page from Wuxiaworld and saves it into the folder where the programm is located"""


def download(link, file_name):
    url = urllib.request.Request(
        link,
        data=None,
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
        }
    )

    with urllib.request.urlopen(url) as response, open(file_name, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)

    """Extract Text from Wuxiaworld html file and saves it into a seperate xhtml file"""


def clean(file_name_in, file_name_out):
    has_spoiler = None
    raw = open(file_name_in, "r", encoding="utf8")
    soup = BeautifulSoup(raw, 'lxml')
    chapter_title = soup.find(class_="caption clearfix")
    content = chapter_title.find_next_sibling(class_="fr-view")
    chapter_title = chapter_title.find("h4")
    if chapter_title.attrs["class"][0] == "text-spoiler":
        has_spoiler = chapter_title.text
        chapter_title = "Chapter name hidden due to potential spoilers"
    else:
        chapter_title = chapter_title.text

    for a in content.find_all("a"):
        a.decompose()
    raw.close()

    html_tmpl ='''<?xml version="1.0" encoding="utf-8"?>
    <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
      "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
    <html xmlns="http://www.w3.org/1999/xhtml">
        <head>
            <title> %(chapter_title)s </title>
        </head>
        <body>
            <h1> %(chapter_title)s </h1>
            %(content)s
            %(spoiler)s
        </body>
    </html>
    '''

    file = open(file_name_out, "w", encoding="utf8")
    if has_spoiler == None:
        file.write(html_tmpl % {"chapter_title": chapter_title,
                                "content": content.decode_contents(),
                                "spoiler": ""})
    else:
        file.write(html_tmpl % {"chapter_title": chapter_title,
                                "content": content.decode_contents(),
                                "spoiler": "<strong>The chapter name is: " + has_spoiler + "</strong>"})
    os.remove(file_name_in)


"""Displays and updates the download progress bar"""


# This function is not used anymore but may be added later on.
# Still fully functional though
def update_progress(progress):
    barLength = 25  # Modify this to change the length of the progress bar
    status = ""
    if isinstance(progress, int):
        progress = float(progress)
    if not isinstance(progress, float):
        progress = 0
        status = "error: progress var must be float\r\n"
    if progress < 0:
        progress = 0
        status = "Halt...\r\n"
    if progress >= 1:
        progress = 1
        status = "Done...\r\n"
    block = int(round(barLength * progress))
    text = "\rDownload Progress: [{0}] {1}% {2}".format("#" * block + "-" * (barLength - block), progress * 100, status)
    sys.stdout.write(text)
    sys.stdout.flush()


""" This will download a cover, calculating the average complementary color
    and will wirte the chapter range on the upper half of the cover centered
    in the before mentioned color.
    Todo: Improve CCR to ignore bright parts of cover's that makes text sometimes
    hard to read."""


def cover_generator(src, starting, ending):
    urllib.request.urlretrieve(src, "cover.jpg")
    img = Image.open("cover.jpg")
    msg = str(starting) + "-" + str(ending)
    draw = ImageDraw.Draw(img)
    thefont = ImageFont.truetype("arial.ttf", 75)
    # Get's the average complementary color of the picutre
    W, H = (400, 600)
    img2 = img.resize((1, 1))
    redc = 255 - img2.getpixel((0, 0))[0]
    greebc = 255 - img2.getpixel((0, 0))[1]
    bluec = 255 - img2.getpixel((0, 0))[2]
    complementary = (redc, greebc, bluec)
    w, h = draw.textsize(msg, font=thefont)
    # Allig's and writes the text
    draw.text(((W - w) / 2, 2), msg, complementary, font=thefont)
    img.save("cover.jpg")


""" Saves downloaded xhtml files into the epub format while also
    generating the for the epub format nesessary container, table of contents,
    mimetype and content files
    ToDo: Generaliseing this part of the code and make it standalone accessible.
    Sidenote: Will take a lot of time."""


def generate(html_files, novelname, author, chaptername, chapter_s, chapter_e, cleanup=True):
    epub = zipfile.ZipFile(novelname + "_" + chapter_s + "-" + chapter_e + ".epub", "w")

    # The first file must be named "mimetype"
    epub.writestr("mimetype", "application/epub+zip")

    # The filenames of the HTML are listed in html_files
    # We need an index file, that lists all other HTML files
    # This index file itself is referenced in the META_INF/container.xml
    # file
    epub.writestr("META-INF/container.xml",
                  '''<?xml version="1.0" encoding="UTF-8"?>
                  <container version="1.0" 
                     xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
                     <rootfiles>
                        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
                     </rootfiles>
                  </container>
                  ''')

    # The index file is another XML file, living per convention
    # in OEBPS/content.xml
    uniqueid = uuid.uuid1().hex

    index_tpl = '''<?xml version="1.0" encoding="utf-8"?>
    <package version="2.0" unique-identifier="BookId" xmlns="http://www.idpf.org/2007/opf">
        <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
            %(metadata)s
        </metadata>
        <manifest>
            <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
            <item id="cover" href="cover.jpg" media-type="image/jpeg" properties="cover-image"/>
            %(manifest)s
        </manifest>
        <spine toc="ncx">
            %(spine)s
        </spine>
    </package>
    '''

    manifest = ""
    spine = ""
    metadata = '''<dc:title>%(novelname)s</dc:title>
        <dc:creator opf:role="aut" opf:file-as="%(author)s">%(author)s</dc:creator>
        <dc:language>en</dc:language>
        <meta name="Sigil version" content="0.9.6" />
        ''' % {
        "novelname": novelname + ": " + chapter_s + "-" + chapter_e, "author": author}

    toc_tmpl = '''<?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN"
       "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
    <ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
      <head>
        <meta name="dtb:depth" content="2"/>
        <meta name="dtb:totalPageCount" content="0"/>
        <meta name="dtb:maxPageNumber" content="0"/>
      </head>
      <docTitle>
        <text>%(novelname)s</text>
      </docTitle>
      <navMap>
        %(toc_mid)s
      </navMap>
    </ncx>
    '''

    nav_point_tmpl = '''<navPoint id="navPoint-%(num)d" playOrder="%(num)d">
        <navLabel>
          <text>%(chapter_title)s</text>
        </navLabel>
        <content src="%(chapter_file_path)s"/>
      </navPoint>
    '''

    toc_mid = ""

    # Write each HTML file to the ebook, collect information for the index
    for i, html in enumerate(html_files):
        basename = os.path.basename(html)
        chapter_file_path = "text/" + basename

        # Append for index
        manifest += '<item id="file_%s" href="%s" media-type="application/xhtml+xml"/>\n' % (
            i + 1, chapter_file_path)
        spine += '<itemref idref="file_%s"/>\n' % (i + 1)

        # Append for TOC
        chapter_title = find_between(html_files[i])
        chapter_title = str(chapter_title)
        toc_mid += nav_point_tmpl % {"num": (i + 1), "chapter_title": chapter_title, "chapter_file_path": chapter_file_path}

        epub.write(html, "OEBPS/text/" + basename)

    # Finally, write the index
    epub.writestr("OEBPS/content.opf", index_tpl % {
        "metadata": metadata,
        "manifest": manifest,
        "spine": spine,
    })

    # Write the TOC
    epub.writestr("OEBPS/toc.ncx", toc_tmpl % {"novelname": novelname, "toc_mid": toc_mid})

    epub.write("cover.jpg", "OEBPS/cover.jpg")
    epub.close()
    os.remove("cover.jpg")

    # removes all the temporary files
    if cleanup:
        print("Cleaning up...")
        for html_file in os.listdir(novelname):
            os.remove(os.path.join(novelname, html_file))
        os.rmdir(novelname)
