# Submit Training End-to-End Verification Sample Suite

This sample directory provides containerized verification of the TrainSwarm Client `submit-training` workflow connecting with the Coordinator API via Docker.

## Structure

- `setup.py`: Launches Coordinator and Client containers over a Docker bridge network (`trainswarm-test-net`).
- `clean.py`: Stops and removes test containers, network, and temporary artifacts.
- `e2e-test.py`: Runs a 5-scenario test matrix executing `docker exec` against the Client CLI.
