# SFS (Symbolic File System)

*A command line utility that provides a lightweight setup for organizing and backing up files*

SFS stores files from a variety of sources, aka collections, that may include directories and
removable media, as symbolic links to the source files.
It also stores the metadata of the source files so that files can later be queried without having to
plug in the source media. 

An SFS is a managed directory which is initialized with the command: `sfs init`. All commands to
be executed in the context of an individual SFS must be run from within the SFS directory tree.
Files are added using the command `sfs add-col my_collection /path/to/source` (add collection).
*SFS Files* are symlinks to source files in added collections. Foreign links and other files can
also exist in an SFS but they are not managed by it and are mostly ignored.

#### Use Cases

 - __Organizing Data Across Discs__ 
     
     SFS was built with the motivation of being able to have a combined view of data stored across
     multiple discs, organize the data in the view and reflect changes back to source discs. This
     is an effortless way of organizing content across discs which is otherwise painfully slow
     and limited as we can operate on a limited number of discs simultaneously and inter disc transfers
     are very slow. Since all operations in an SFS are performed within the same disc and on symlinks
     instead of heavy files, they are much faster
     
     __Note:__ To view the content of a file we obviously do need the source to be available. So, if 
     there is a need of viewing file content while organizing them, the source needs to be plugged in which
     might or might not be appropriate for all use cases. However, SFS makes it easy to query the 
     source of an SFS File when it is needed to be accessed
      
 - __Backing up Files__
    
    While there are lots of ways to make direct backups of directories, an SFS allows you to organize
    the content while backing them up and potentially saving them to multiple destinations with a single command.
    For exaback themmple, you might have an SFS in which you add local files, like multimedia and documents, organize
    them in hierarchies resembling your storage hierarchies, then map the top-level SFS directories to backup
    destinations and preform the backup with a single save command. Periodically, you will have to synchronize
    the SFS, sort the newly added local files and rerun the backup.

 - __Decouple Data Storage and View__
 
    Data often needs to be stored in a certain way which might not be similar to the hierarchy in which you want
    to view it. SFS allows you to create a virtual hierarchy for viewing content. For example, consider that you have
    data saved in a number of discs or directories, organized as music, documents, projects, etc. Your options are
    either to keep a copy of the important files locally, which we commonly do, or to plugin all the media one by
    one and search for the files you need, which hopefully no one does. You can instead create an SFS instance,
    dump all your discs into it, create a directory in the SFS for local files and copy all needed files to your
    local system. You can search for files in all your discs locally and, periodically, you can update what files to be
    kept in you local system

#### Commands
    # SFS Operations
    init            Initialize a new SFS in the current directory
    is-sfs          Check whether a path is inside an SFS
    
    # Collection Operations
    add-col         Add a named collection to the current SFS
                    -n, --name
                        Collection name (defaults to source root directory name)
    is-col          Check whether a path is inside any collection added to the current SFS
    list-cols       List all collections in the current SFS
    del-col         Delete a collection and associated symllinks from 
                    the current SFS    
    sync-col        Synchronize any changes made to a collection (addition, 
                    modification and deletion of files)
    
    # Querying SFS files
    query           Query metadata of a file or directory in an SFS
    
    # Deduplication
    find-dups      Check for duplicate files (by name and size) recursively 
                   in a target directory and save dulicates to a JSON file
                   in the target directory
                   -o, --override
                        Override the generated JSON file if it exists
                   -d, --del-duplicates
                        Mark duplicates (all but first in a list of duplicate files) for deletion
    dedup          Use the JSON file (after manually choosing which files to
                   keep) to delete duolicates in a target directory
                   -d, --del-json
                        Delete the generated JSON file after a successful de-deuplication
                   
    # Merge
    merge          Merge two non-nested directories in an SFS. In case of merge
                   conlicts, the process terminates after saving conflicting files
                   to a JSON. The file can be edited and used for completing the
                   merge operation
                   -k, --on-conflict
                        Conflict resoution can be one of keep-target, keep-source or keep-both
                   -c, --continue
                        Use specified or default conflict rsolution without saving conflicts JSON
                   -j, --json
                        Use the generated JSON file for handling conflicts 
                   -o, --override
                        Override the generated JSON file if it exists
                   -d, --del-json
                        Delete the generated JSON file after a successful merge
                   -s, --del-source
                        Delete the source directory after a successful merge
                   
#### Usage

Install with pip

    pip install symbolic-file-system

Or clone this repo and run setup directly

    python3 setup.py install
    
Access all SFS commands through the installed script named *sfs*

    mkdir my-first-sfs
    cd my-first-sfs
    sfs init
    sfs add-col my-hdd /media/hdd
    
You can run tests with nose
    
    nosetests
    
#### Work in Progress

 - __Saving Changes Made Back to Source__ 
     
     Any changes made to the organisation of links in an SFS, like deletion, renaming 
     or relocation will be reflected back to the source discs or directories. There will
     be a number of modes of saving changes:
      - __Copy__: Files will be copied to an actual directory or drive with the same file
      hierarchy as some directory in an SFS, the copied files being actual source files
      from various collections
      - __Move__: The source files will be moved to a new destination as specified by the
      SFS file hierarchy and save mapping
      - __Delete__: Files deleted in an SFS will be reflected back to a collection source
       or a part of it
      - __Save__: In this mode, an exhaustive mapping of SFS directories and collection
      sources will be specified and changes will be reflected in all collections, internally
      executing __Move__ and __Delete__ on all of them
      
 - __Filtering Files__

    SFS will add the ability to filter SFS Files and directories, a feature missing from most
    file systems. The following filters will be available:
     - Filter by file size
     - Filter by file type
     - Filter by any custom properties
    
 - __Adding Properties to Files and Directories__
 
    It will be possible to add properties to files and directories in an SFS an look them up which can be useful
    for simply tagging them and can even be used while applying filters
 
 - __Freezing Directories__
 
    *Freeze* will be a special property that can be applied to directories in an SFS to prevent
    them from being manipulated by SFS commands like Merge, Filters and De-duplication. This
    can be useful for hierarchies like project and application directories which must remain intact
    
    
#### Tips

 - Though SFS is all about symlinks and your source files are always safe, it is recommended to back
 up the SFS root directory before doing anything adventurous. Backing up is as simple is making a 
 copying os the SFS root directory
