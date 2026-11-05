#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ComponentState {
    pub name: String,
    pub version: String,
    pub is_healthy: bool,
}

#[derive(Debug, Default)]
pub struct SystemHealthReporter {
    components: Vec<ComponentState>,
}

impl SystemHealthReporter {
    pub fn new() -> Self { Self { components: Vec::new() } }
    pub fn register(&mut self, name: &str, ver: &str, healthy: bool) {
        self.components.push(ComponentState { name: name.into(), version: ver.into(), is_healthy: healthy });
    }
    pub fn all_healthy(&self) -> bool {
        self.components.iter().all(|c| c.is_healthy)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_system_health_reporter_aaa() {
        // Arrange
        let mut reporter = SystemHealthReporter::new();
        reporter.register("SigmaOS-kernel", "1.0.0", true);
        reporter.register("SigmaOS-shell", "1.0.0", true);
        // Act & Assert
        assert!(reporter.all_healthy());
    }
}
