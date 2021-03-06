import os
import collections
import xml.etree.ElementTree
import WikidotHelpers

#TODO: Need to deal with accented letter (e.g. Farmer)
#TODO: Need to deal with embedded hyperlinks (e.g., Ansible)
#TODO: Need to deal with ALL-CAPS (are we ignoring all of the pages we ought to be?)

log = open("log.txt", "w")

def logger(message):
    print(message, file=log)
    print(message)


#*******************************************************************************
# Generate the Wikimedia canonicized form of a name
# Note that for now we are ignoring the possibility of namespace: prefixes
def MediawikiCanonicize(name):
    if name is None or name is "":
        return name

    # Underscores are treated as spaces
    name=name.replace("_", " ")

    # Leading and trailing spaces and underscores are ignored
    name=name.strip()

    # Multiple consecutive spaces are treated as a single space
    while "  " in name:
        name=name.replace("  ", " ")

    # Wikimedia always treats the 1st character as capital
    name=name[:1].upper()+name[1:]

    return name


#*******************************************************************************
# Define the PageInfo tuple
PageInfo=collections.namedtuple("PageInfo", "Title, CanName, Tags, Links, Redirect")


#==================================================================
# Load the pages in the site directory
def LoadDirectory(site, dir):
    if not os.path.isdir(dir):
        return

    # First deal with any pages in this directory
    for (dirpath, dirnames, filenames) in os.walk(dir):
        break

    filenames=[os.path.splitext(f)[0] for f in filenames if os.path.splitext(f)[1].lower() == ".txt"]
    for fname in filenames:
        LoadPage(site, dirpath, fname)


#==================================================================
# Load a single page
# Locate its links and add this page to the lists of pages that this page points to
def LoadPage(site, dirpath, fname):

    if fname.startswith("index_"):
        return

    pathname=os.path.join(dirpath, fname)

    # Read the tags and title from pathname.xml
    e=xml.etree.ElementTree.parse(pathname+".xml").getroot()
    title=e.find("title").text

    tagsEl=e.find("tags")
    tags=None
    if tagsEl is not None:
        tags=[t.text for t in tagsEl.findall("tag")]

    #print(fname)

    f=open(os.path.join(pathname+".txt"), "rb") # Reading in binary and doing the funny decode is to handle special characters embedded in some sources.
    source=f.read().decode("cp437")
    f.close()

    def IsRedirect(pageText):
        pageText=pageText.strip()  # Remove leading and trailing whitespace
        if pageText.lower().startswith('[[module redirect destination="') and pageText.endswith('"]]'):
            return pageText[31:].rstrip('"]')
        return None

    # First, check to see if this is a redirect.  If it is, we're done.
    redirect=IsRedirect(source)
    if redirect:
        site[fname]=PageInfo(title, fname, tags, None, redirect)
        return

    # Now we scan the source for links.
    # A link is one of these formats:
    #   [[[link]]]
    #   [[[link|display text]]]
    links=set()    # Links is a *set* of all the unique pages pointed to by this page. (We use the set because we don't care about order, but do care about duplicates.)
    while len(source) > 0:
        loc=source.find("[[[")
        if loc == -1:
            break
        loc2=source.find("]]]", loc)
        if loc2 == -1:
            break
        link=source[loc+3:loc2]
        # Now look at the possibility of the link containing display text.  If there is a "|" in the link, then only the text to the left of the "|" is the link
        if "|" in link:
            link=link[:link.find("|")]
        links.add(link.strip())
        # trim off the text which has been processed and try again
        source=source[loc2:]

    site[fname]=PageInfo(title, fname, tags, links, None)

    return

# *****************************************************************
# *****************************************************************
# Main

root=r"C:\Users\mlo\Documents\usr\Fancyclopedia\Python\site"
fileReport=open("Report.txt", "w")

# Walk the directory structure under root
# We want the following information for each existing page:
#   Its title
#   Its canonical name
#   Its tags
#   Its Links (a list of the exact link text for each link)
#   If it is a redirect, the exact text of the redirect page name
# This will be stored as a dictionary indexed by the page's cannonical name
# The value will be a tuple: (Title, CanName, Tags, list of Links, Redirect)

# Note that each page has *four* components in the site image on disk:
#   <name>.txt -- the source text
#   <name>.xml -- xml containing (among other things) the tags
#   <name>.html> -- the html generated by Wikidot from the source
#   <name> as a directory -- if there are attached files, a directory named <name> containing the files

site={}
LoadDirectory(site, root)

# Now we have a complete map of the links in site.  All the page names are "raw" -- as they were in the wiki.  None have been canonicized.
# The map lists the links *leaving* each page.  We want to generate the inverted map showing the links *in* to each page.

#-----------------------------------
def AddLink(inverseSite, link, name):
    if link in inverseSite:
        inverseSite[link].append(name)
    else:
        inverseSite[link]=[name]
#-----------------------------------


# InverseSite is a dictionary of all outgoing links in the site (existing or not) in their exact form.  Each contains a list of the pages that name it.
inverseSite={}
for (key, val) in site.items():
    if val.Links is not None:
        for link in val.Links:
            AddLink(inverseSite, link, key)
    else:
        if val.Redirect is not None:
            AddLink(inverseSite, val.Redirect, key)

# The main issue we're looking at is the Wikimedia canoniczation. Wikimedia does a much weaker canonization than does Wikidot, so links which
# Wikidot interprets correctly will be routed to non-existant pages by Wikimedia.
# We want inverseKeys to be sorted so that all pages that Wikidot sees as the same are sorted together.
# Within a group of pages which are Wikidot-identical, we want to sort in order by their Wikimedia canonical forms.
# Within each smaller group, we'll sort by the actual link text
# We'll then list all links that are used in Wikidot which map to different Wikimedia pages.
inverseKeys=list(inverseSite.keys())
inverseKeys.sort(key=lambda elem: elem)
inverseKeys.sort(key=lambda elem: MediawikiCanonicize(elem))
inverseKeys.sort(key=lambda elem: WikidotHelpers.Cannonicize(elem))


#-----------------------------------
def tempPrint(line, f):
    try:
        print(line, file=f)
    except:
        print("***** Warning. Character ugliness follows!", file=f)
        print(line.encode("UTF-8"), file=f)
#-----------------------------------
def FormatPageList(inverseSite, key):
    maxPages=4
    pages=inverseSite[key]
    line=""
    for i in range(0, min(maxPages, len(pages))):
        if i > 0:
            line+=",  "
        line+="'"+pages[i]+"'"
    if len(pages) > maxPages:
        line+=",  plus "+str(len(pages)-maxPages)+" more..."
    return line
# -----------------------------------
def PrintPageList(f, inverseSite, key):
    tempPrint(FormatPageList(inverseKeys, key), f)
# -----------------------------------


# Generate a report on all pages where there are linkage problems
fileMultiple=open("Pages with multiple linking forms.txt", "w")
fileDump=open("Dump of process output.txt", "w")

# We're going to group on three levels:
#   Wikidot Cannonical From
#       Wikimedia Canonical Form
#           Actual linkage
# We only want to print when a single Wikidot Canonical Form has more than one Mediawiki Canonical Forms.  Then we want to list the actual linkages separately
outerKey="nonsense"
innerKey="random string"
savedLinesArray=[]
savedLine=""
count=0
for key in inverseKeys:
    tempPrint("\nnew key="+key, fileDump)
    # Is this the first record of a new Wikidot canonical name (outer key)?
    if WikidotHelpers.Cannonicize(outerKey) != WikidotHelpers.Cannonicize(key): # The outer key changes only when it's Wikidot Canonical form changes
        tempPrint("outer key changed from  "+WikidotHelpers.Cannonicize(outerKey)+"  to  "+WikidotHelpers.Cannonicize(key), fileDump)

        # If there were two or more inner keys in the previous outer key, print them
        if len(savedLinesArray) > 0 and len(savedLine) > 0:
            count+=1
            savedLinesArray.append(savedLine)
            tempPrint("len(savedLinesArray)="+str(len(savedLinesArray)), fileDump)
            tempPrint("\n"+outerKey, fileMultiple)
            for l in savedLinesArray:
                tempPrint(l, fileMultiple)
                tempPrint("    "+l, fileDump)

        # Now deal with the new outer key
        outerKey=key
        innerKey=key
        savedLinesArray=[]
        savedLine=""

        # And save the line for this record.
        savedLine="'"+key+"' <=== "+FormatPageList(inverseSite, key)
        tempPrint("saved: "+FormatPageList(inverseSite, key), fileDump)
        continue

    # The outer key has not changed.  Is the inner key the same, also?
    if MediawikiCanonicize(innerKey) == MediawikiCanonicize(key):   # The inner key changes  when it's Mediawiki Canonical form changes
        tempPrint("innerKey same:  "+MediawikiCanonicize(innerKey)+"   Saved: "+FormatPageList(inverseSite, key), fileDump)
        savedLine=savedLine+FormatPageList(inverseSite, key)
        continue

    # Outer key has not changed, but the inner key is different.  Save the saved lines and go again
    tempPrint("innerKey changed from "+MediawikiCanonicize(innerKey)+"  to  "+MediawikiCanonicize(key), fileDump)
    savedLinesArray.append(savedLine)

    savedLine="'"+key+"' <=== "+FormatPageList(inverseSite, key)  # Begin a new list of lines
    tempPrint("saved: "+FormatPageList(inverseSite, key), fileDump)
    innerKey=key

print("Keys with multiple formats:  "+str(count))
print("Keys with multiple formats:  "+str(count), file=fileReport)
fileMultiple.close()


# Next, we do an analysis of redirects and make a list of all redirects where the target link is all lower case. (These are probably wrong.)
fileLowerRedirects=open("Redirects Which Are Lowercase.txt", "w")
count=0
for (key, val) in site.items():
    if val.Redirect is not None:
        if val.Redirect == val.Redirect.lower() and not val.Redirect.isdigit():
            tempPrint(key+"  ==>  "+val.Redirect, fileLowerRedirects)
            count+=1

print("Lowercase redirects:  "+str(count))
print("Lowercase redirects:  "+str(count), file=fileReport)
fileLowerRedirects.close()


# Generate a list of double redirects
fileDoubleRedirects=open("Double Redirects.txt", "w")
count=0
for (key, val) in site.items():
    if val.Redirect is not None:
        pageT=val.Title
        pageCR=WikidotHelpers.Cannonicize(val.Redirect)
        if pageCR not in site.keys():
            continue
        if site[pageCR].Redirect is not None:
            pageRT=site[pageCR].Title
            pageRCR=WikidotHelpers.Cannonicize(site[pageCR].Redirect)
            if pageRCR not in site.keys():
                tempPrint(pageT+"  ==>  "+pageRT+"  ==>  (missing) "+pageRCR, fileDoubleRedirects)
                count+=1
                continue
            pageRRT=site[pageRCR].Title
            tempPrint(pageT+"  ==>  "+pageRT+"  ==>  "+pageRRT, fileDoubleRedirects)
            if site[pageRCR].Redirect is not None:
                pageRRT=site[pageRCR].Title
                pageRRCR=WikidotHelpers.Cannonicize(site[pageRCR].Redirect)
                if pageRRCR not in site.keys():
                    tempPrint(pageT+"  ==>  "+pageRT+"  ==>  "+pageRRT+"  ==>  (missing) "+pageRRCR, fileDoubleRedirects)
                    count+=1
                    continue
                pageRRRT=site[pageRRCR].Title
                tempPrint(pageT+"  ==>  "+pageRT+"  ==>  "+pageRRT+"  ==>  "+pageRRCR, fileDoubleRedirects)
                count+=1

print("Double redirects:  "+str(count))
print("Double redirects:  "+str(count), file=fileReport)
fileDoubleRedirects.close()

# Generate  a list of redirects with missing targets
fileMissingRedirect=open("Missing Redirect Target.txt", "w")
count=0
for (key, val) in site.items():
    if val.Redirect is not None:
        pageT=val.Title
        pageCR=WikidotHelpers.Cannonicize(val.Redirect)
        if pageCR not in site.keys():
            tempPrint(pageT+"  ==>  "+pageCR, fileMissingRedirect)
            count+=1

print("Missing redirect targets:  "+str(count))
print("Missing redirect targets:  "+str(count), file=fileReport)
fileMissingRedirect.close()

fileReport.close()