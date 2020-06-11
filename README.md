[![Build Status](https://travis-ci.org/C3BI-pasteur-fr/ReGaTE.svg?branch=master)](https://travis-ci.org/C3BI-pasteur-fr/ReGaTE)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/crs4/ReGate)![GitHub](https://img.shields.io/github/license/crs4/ReGaTE)

ReGaTE
==================

ReGaTE is a command line utility that supports the registration of tools and workflows installed on any given Galaxy portal in ELIXIR bio.tools and viceversa.



## How to install

1) Clone this Git repository and install *ReGaTE* via `pip`:

```[language="bash"]
pip install .
```

2) type `regate template` to generate your `regate.ini` configuration file and fill it with your Galaxy and bio.tools platform settings. In particular, you need  (e.g., `galaxy_url_api`, `api_key`, `bioregistry_host`, etc.)


You can also opt to use the docker image:  `docker pull crs4/regate`.  Take care
to mount appropriate directories to access the configuration file and store
metadata.


## Getting started

Type `regate` to run `ReGaTE` interactively:

<img src="doc/media/ReGaTE.gif?raw=true" width="100%">



A wizard will guide you through the main steps of the ReGaTE use:

* choose which *source* platform to export from: `galaxy`, `biotools`;
* choose whether push or not the exported resources to the *target* platform (i.e., `biotools` if the *source* is `galaxy` or viceversa);
* which type of resource to export: `tools`, `workflows`, `all`;
* which resources to export.

As a result of the *export* process, all the exported resources will be placed into the configurable output folder `regate_tools` and registered on the target platform. 

```[language=bash]
 regate_tools/
 |—— galaxy/
 |   |—— tools/
 |   |    |—— not_imported/
 |   |—— workflows/
 |—— biotools/
 |   |—— tools/
 |   |—— workflows/
```
*Layout of the`regate_tools` folder. It is first organised by platform (i.e., `galaxy`,`biotools`) and then by resource type (i.e., `tool`, `workflow`)*



## Usage
You can run `regate` to export and/or push tools and/or workflows without prompting:

```bash
regate --no-interactive export 
       --from [galaxy|biotools] [--push] [tools|workflows|all] [--filter id1,...,idN]
```

* use the `--push` option to export and push the tools/workflows with a single run
* the `--filter` option followed by a comma-separated IDs of workflows/tools allows you to apply the export/push only to a limited set of resources



If you choose to skip the *push* process, you can still use the exported resources within the `regate_tools` folder to register them to the target platform through the `push` subcommand. For example, to push previously exported workflows to ELIXIR bio.tools you can type:

```
regate push --to galaxy workflows
```

*Example of regate usage to register workflows exported from the Galaxy platform to ELIXIR bio.tools*




### Usage examples

The following examples illustrate the main typical use cases.

#### Register Galaxy tools and workflows on ELIXIR bio.tools

To export tools and/or workflows from Galaxy you can launch `regate` with a syntax like this:


```bash
regate --no-interactive export 
       --from galaxy [--push] [tools|workflows|all] [--filter id1,...,idN]
```

When publishing a workflow from Galaxy on bio.tools, ReGaTE will serialize the
workflow and store it on bio.tools as a DataURI along with the available
metadata.  When importing a workflow from  bio.tools into Galaxy the inverse
operation takes place:  the serialized workflow is downloaded from bio.tools and
imported into Galaxy through its API.

##### Examples

###### 1) Export all tools from Galaxy to the bio.tools format

```
regate --no-interactive export --from galaxy tools
```

###### 2) Export a list tools from Galaxy to the bio.tools format

```
regate --no-interactive export --from galaxy tools \
       --filter ChangeCase,CONVERTER_cml_to_inchi
```


###### 3) Push one exported tool to ELIXIR bio.tools

```
regate --no-interactive push --to biotools tools --filter ChangeCase
```

###### 4) Export and push all workflows from Galaxy to ELIXIR bio.tools

```bash
regate --no-interactive export --from galaxy --push workflows
```



#### Register bio.tools tools and workflows on Galaxy

ELIXIR bio.tools tools and workflows can be imported to a Galaxy instance if they have been registered on ELIXIR through the ReGaTE tool. 

**Notice.** The following warnings apply to tools and workflows you want to export from bio.tools and import into a Galaxy instance:

1. *tools and workflows on bio.tools have been registered through ReGaTE*
2. *only Galaxy tools associated with a Tool Shed repository can be reimported on a Galaxy instance*. The current implementation of ReGaTE uses the Tool Shed to install tools on Galaxy. Thus, tools which are not associated with a Tool Shed can only be exported from bio.tools but not imported into Galaxy. To mitigate this limitation, as a result of the export process, for each tool `X` of thoose tools you will find a folder `X` —  under the `regate_tools/galaxy/tools/not_imported` path — containing the tool wrapper definition in JSON format (as it comes from the export process) and the tar.gz archive which allows you to manually install the tool on your Galaxy instance.
3. *Galaxy workflows* — registered on the ELIXIR bio.tools platform through the ReGaTE tool — *can always be imported on a Galaxy instance*.

##### Examples
###### 1) Export and push all tools from ELIXIR bio.tools to a Galaxy instance

```
regate --no-interactive export --from biotools --push tools
```

###### 2) Export and push all workflows from ELIXIR bio.tools to a Galaxy instance

```
regate --no-interactive export --from biotools --push workflows
```
