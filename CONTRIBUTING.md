# Contributing

Open an [issue](https://github.com/mostafanasrrsp/cn-community-codec/issues) for a result, feature idea or bug. Pull requests are welcome.

## Share a file comparison

1. Give the preview version, operating system, Python version and hardware. Identify the file family, byte size and an upstream link or a shareable minimal example. You can keep private originals on your machine.
2. Include the pack command, selected frame type, full output size, strongest conventional control you tried and its version and settings. If reporting speed, say which steps were timed, how often you repeated them and whether startup and disk access were included.
3. Restore the frame and compare the restored file with the original. Record whether the contents matched. Report files that grow, resource costs and cases where the conventional control wins.

## Change the code

From the repository root, rebuild the preview and run the portable tests before submitting a patch.

```sh
python3 preview/build_preview.py
python3 preview/test_preview.py
(cd community_codec && python3 -m unittest discover -s tests)
```

The builder writes the executable to `preview/cn-preview.pyz`. Keep the root executable as the shipped preview for comparisons. Changes to a wire format should include a description, an example frame, a corruption case and the expected behavior with earlier versions. For a new compression method, include an existing approach as a control and reproduce a byte-for-byte restore.
