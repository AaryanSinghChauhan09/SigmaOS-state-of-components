    # SigmaOS-state-of-components

    Dashboard of component health & parity gaps

    Part of the **SigmaOS** sovereign operating-system ecosystem — a multi-repository
    distribution modelled on Linux Mint and Omarchy Linux. See the parent
    [`SigmaOS`](https://github.com/AaryanSinghChauhan09/SigmaOS) repository for the
    full component index.

    ## Upstream inspirations
    - https://github.com/omacom/state-of-omarchy

    ## Design principles applied
    - **Pure Functions**
- **Deterministic Testing**
- **Fail-Fast**
- **Least Astonishment**
- **KISS**

    ## Usage
    Verbs: `snapshot, diff, gaps, score`

    ```
    $ sigma-state snapshot --facts inventory.json --out snap.json
$ sigma-state diff --before old.json --after new.json
$ sigma-state gaps --snapshot snap.json --required required.txt
$ sigma-state score --snapshot snap.json

    ```

    ## Build & test
    ```
    make build
    make test
    ```

    ## Licence
    GNU General Public License v3.0 (FOSS).
